"""
Route-level tests for the photo analysis endpoint.

CI does not install the heavy deps (supabase, opencv,
ultralytics) that ``app.routes.photo_analysis`` imports at
module level. To keep this CI-safe we stub those modules in
``sys.modules`` before importing the router, then monkeypatch
the per-photo analysis functions for deterministic behavior.
"""

import os
import sys
import types
from datetime import datetime

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///:memory:",
)

import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base, get_db  # noqa: E402
from app.models.device import Device  # noqa: E402
from app.models.inspection import Inspection  # noqa: E402
from app.models.inspection_photo import InspectionPhoto  # noqa: E402


class _FakeStorage:
    def from_(self, bucket):
        return self

    def download(self, path):
        return b"fake-image-bytes"


class _FakeSupabase:
    storage = _FakeStorage()


def _seed_stub_modules():
    """Inject fake heavy-dependency modules before import."""

    def _stub(name, **attrs):
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module

    if "app.core.supabase" not in sys.modules:
        _stub("app.core.supabase", supabase=_FakeSupabase())

    if "app.services.photo_analyzer" not in sys.modules:
        _stub(
            "app.services.photo_analyzer",
            analyze_image=lambda image_bytes: {},
        )

    if "app.services.condition_analyzer" not in sys.modules:
        _stub(
            "app.services.condition_analyzer",
            analyze_condition=lambda image_bytes=None,
            photo_type=None: None,
        )


_seed_stub_modules()

from app.routes import photo_analysis as photo_analysis_route  # noqa: E402


def _fake_photo_analysis(image_bytes):
    return {
        "quality_score": 85,
        "quality_grade": "Good",
        "phone_detection": {
            "detected": True,
            "confidence": 0.95,
        },
        "blurriness": 0.2,
        "brightness": 0.6,
    }


def _fake_condition(image_bytes=None, photo_type=None):
    return {
        "visible_damage_score": 5.0,
        "confidence": 0.9,
        "condition_text": "Minor wear on edges.",
    }


class TestPhotoAnalyze:
    def _client(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        Base.metadata.create_all(engine)

        def _get_test_db():
            db = Session(engine)
            try:
                yield db
            finally:
                db.close()

        app = FastAPI()
        app.include_router(photo_analysis_route.router)
        app.dependency_overrides[get_db] = _get_test_db
        return TestClient(app), engine

    def _canned_analysis(self, condition_score=95):
        return {
            "inspection_code": "any",
            "photos_analyzed": 6,
            "overall_photo_quality": 85,
            "overall_grade": "Excellent",
            "physical_condition_ai": {
                "status": "completed",
                "condition_score": condition_score,
                "effective_condition_score": 85,
                "condition_grade": "Excellent",
                "average_confidence": 0.9,
                "detected_views": 6,
                "total_views": 6,
            },
            "photos": [
                {
                    "photo_type": "front",
                    "analysis": {
                        "quality_score": 85,
                        "physical_condition": {},
                    },
                }
            ],
        }

    def _cube_market_price(self, market_price=24000):
        def _fake(device):
            return (market_price, market_price, "ml score")

        return _fake

    def _create_inspection(
        self,
        engine,
        codes=("front", "back", "left", "right", "top", "bottom"),
    ):
        db = Session(engine)

        device = Device(
            brand="Vivo",
            model="S2 5G",
            storage="8GB + 128GB",
            created_at=datetime.now().isoformat(),
        )
        db.add(device)
        db.flush()

        inspection = Inspection(
            inspection_code="INS-2026-PHOTOTEST1",
            device_id=device.id,
            inspection_type="photo_inspection",
            status="created",
        )
        db.add(inspection)
        db.flush()

        for index, code in enumerate(codes):
            db.add(
                InspectionPhoto(
                    inspection_id=inspection.id,
                    photo_type=code,
                    storage_path=f"photos/{code}.jpg",
                    content_type="image/jpeg",
                    created_at=datetime.now().isoformat(),
                )
            )

        code = inspection.inspection_code

        db.commit()
        db.close()

        return code

    def test_analyze_success(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_image",
            _fake_photo_analysis,
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_condition",
            _fake_condition,
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "supabase",
            _FakeSupabase(),
        )

        client, engine = self._client()
        code = self._create_inspection(engine)

        response = client.post(
            f"/api/inspections/{code}/analyze"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["inspection_code"] == code
        assert data["overall_grade"] == "Excellent"
        assert (
            data["physical_condition_ai"]["condition_grade"]
            == "Excellent"
        )
        assert data["physical_condition_ai"]["status"] == "completed"

        # (front, back, left, right, top, bottom)
        assert len(data["photos"]) == 6

    def test_analyze_inspection_not_found(self):
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_image",
            _fake_photo_analysis,
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "supabase",
            _FakeSupabase(),
        )

        try:
            client, _ = self._client()

            response = client.post(
                "/api/inspections/INS-0000-NOPE/analyze"
            )

            assert response.status_code == 404
            assert response.json()["detail"] == "Inspection not found"

        finally:
            monkeypatch.undo()

    def test_missing_photos_returns_400_with_missing_list(self, monkeypatch):
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_image",
            _fake_photo_analysis,
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "supabase",
            _FakeSupabase(),
        )

        client, engine = self._client()
        # Only three of the six views captured.
        code = self._create_inspection(
            engine,
            codes=("front", "back", "left"),
        )

        response = client.post(
            f"/api/inspections/{code}/analyze"
        )

        assert response.status_code == 400

        detail = response.json()["detail"]

        assert detail["message"] == "All six photos are required."
        # The three missing views should be reported.
        assert set(detail["missing"]) == {
            "right",
            "top",
            "bottom",
        }

    def test_valuate_happy_path(self, monkeypatch):
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda code, db: self._canned_analysis(),
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            self._cube_market_price(24000),
        )

        client, engine = self._client()
        code = self._create_inspection(engine)

        response = client.post(
            f"/api/inspections/{code}/valuate"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["inspection_code"] == code
        assert data["market_price"] == 24000
        assert data["resale_price"] == round(
            24000 * (0.60 + 0.85 * 0.40)
        )
        assert data["condition_score"] == 85
        assert data["condition_grade"] == "A"
        assert data["valuation_type"] == "AI Photo + ML Valuation"

    def test_valuate_422_when_no_condition(self, monkeypatch):
        analysis = self._canned_analysis()
        analysis["physical_condition_ai"] = {
            "status": "unavailable",
            "condition_score": None,
            "effective_condition_score": None,
        }

        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda code, db: analysis,
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            self._cube_market_price(24000),
        )

        client, engine = self._client()
        code = self._create_inspection(engine)

        response = client.post(
            f"/api/inspections/{code}/valuate"
        )

        assert response.status_code == 422
        assert (
            response.json()["detail"]
            == "Unable to determine physical condition."
        )

    def test_exchange_valuate_happy_path(self, monkeypatch):
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda code, db: self._canned_analysis(),
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            self._cube_market_price(24000),
        )

        client, engine = self._client()
        code = self._create_inspection(engine)

        response = client.post(
            f"/api/inspections/{code}/exchange-valuate",
            json={
                "answers": [
                    {
                        "question_key": "screen",
                        "answer_value": "good",
                    },
                    {
                        "question_key": "battery",
                        "answer_value": "average",
                    },
                ]
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["inspection_code"] == code
        assert data["valuation_type"] == "Complete Exchange Inspection"
        assert data["market_price"] == 24000
        assert data["questionnaire_score"] is not None
        assert data["ai_condition_score"] == 85
        assert data["condition_score"] == round(
            (data["questionnaire_score"] + 85) / 2
        )

    def test_exchange_valuate_falls_back_to_questionnaire(self, monkeypatch):
        analysis = self._canned_analysis()
        analysis["physical_condition_ai"] = {
            "status": "unavailable",
            "condition_score": None,
            "effective_condition_score": None,
        }

        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda code, db: analysis,
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            self._cube_market_price(24000),
        )

        client, engine = self._client()
        code = self._create_inspection(engine)

        response = client.post(
            f"/api/inspections/{code}/exchange-valuate",
            json={
                "answers": [
                    {
                        "question_key": "screen",
                        "answer_value": "excellent",
                    },
                    {
                        "question_key": "battery",
                        "answer_value": "excellent",
                    },
                ]
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["ai_condition_score"] == data["questionnaire_score"]
        assert data["condition_score"] == data["questionnaire_score"]