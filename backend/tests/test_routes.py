"""
Route-level API tests.

These mount only the routers under test (not app.main, which
would pull in heavy/optional deps like supabase that are not
installed in CI). A sqlite URL is used as the DATABASE_URL
fallback so database imports succeed in clean environments.
"""

import os

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///:memory:",
)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.routes import device_prices as device_prices_route  # noqa: E402
from app.routes import health as health_route  # noqa: E402
from app.routes import device_catalog as device_catalog_route  # noqa: E402
from app.routes import inspection as inspection_route  # noqa: E402
from app.routes import ml_valuation as ml_valuation_route  # noqa: E402
from app.routes import photo_analysis as photo_analysis_route  # noqa: E402
from app.routes import photos as photos_route  # noqa: E402

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base, get_db  # noqa: E402


class TestDevicePrices:
    def _client(self):
        app = FastAPI()
        app.include_router(device_prices_route.router)
        return TestClient(app)

    def _fake_lookup(self, exists=True):
        return {
            "exists": exists,
            "matched_model": (
                "Vivo S2 5G" if exists else None
            ),
            "valid_variants": (
                ["8GB + 128GB"] if exists else []
            ),
            "new_price_inr": 24000 if exists else None,
            "used_resale_price_inr": (
                17000 if exists else None
            ),
            "source": (
                "Gemini + ML" if exists
                else "Random Forest ML + Dataset (closest match, unverified)"
            ),
            "confidence": "high" if exists else "low",
            "estimated_price_inr": 15999,
            "estimated_matched_model": "Vivo V29",
            "notes": (
                "New or recently launched device; "
                "price is an estimate from the closest match in the dataset."
            ),
        }

    def test_exists_resolution(self, monkeypatch):
        monkeypatch.setattr(
            device_prices_route,
            "lookup",
            lambda **kwargs: self._fake_lookup(True),
        )

        response = self._client().get(
            "/api/device-prices?brand=Vivo&model=S2 5G&storage=8GB + 128GB"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["resolution"] == "exists"
        assert data["matched_model"] == "Vivo S2 5G"
        assert data["new_price_inr"] == 24000
        assert data["source"] == "Gemini + ML"

    def test_not_found_returns_estimate_fields(self, monkeypatch):
        monkeypatch.setattr(
            device_prices_route,
            "lookup",
            lambda **kwargs: self._fake_lookup(False),
        )

        response = self._client().get(
            "/api/device-prices?brand=Vivo&model=S2 5G&storage=8GB + 128GB"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["resolution"] == "not_found"

        assert data["estimated_price_inr"] == 15999
        assert data["estimated_matched_model"] == "Vivo V29"
        assert data["notes"] is not None
        assert "estimate" in data["notes"].lower()

        assert data["new_price_inr"] is None
        assert data["used_resale_price_inr"] is None

    def test_lookup_error_yields_unknown(self, monkeypatch):
        monkeypatch.setattr(
            device_prices_route,
            "lookup",
            lambda **kwargs: None,
        )

        response = self._client().get(
            "/api/device-prices?brand=Apple&model=iPhone 15&storage=128"
        )

        assert response.status_code == 200
        assert response.json()["resolution"] == "unknown"


class TestDeviceCatalog:
    def _client(self):
        app = FastAPI()
        app.include_router(device_catalog_route.router)
        return TestClient(app)

    def _fake_register(self, **kwargs):
        return {
            "brand": kwargs.get("brand", "Vivo"),
            "model": "S2 5G",
            "ram_gb": 8,
            "storage_gb": 128,
            "storage": "8GB + 128GB",
            "price_inr": kwargs.get("new_price_inr", 24000),
            "added_catalog": True,
            "added_dataset": True,
            "price_cached": True,
        }

    def test_add_device_happy_path(self, monkeypatch):
        monkeypatch.setattr(
            device_catalog_route,
            "register_device",
            self._fake_register,
        )

        response = self._client().post(
            "/api/device-catalog/devices",
            json={
                "brand": "Vivo",
                "model": "S2 5G",
                "storage": "8GB + 128GB",
                "new_price_inr": 24000,
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["brand"] == "Vivo"
        assert data["model"] == "S2 5G"
        assert data["storage"] == "8GB + 128GB"
        assert data["price_inr"] == 24000
        assert data["added_catalog"] is True
        assert data["added_dataset"] is True
        assert data["price_cached"] is True

    def test_add_device_happy_path_without_price(self, monkeypatch):
        captured = {}

        def fake_register(**kwargs):
            captured.update(kwargs)
            return self._fake_register(**kwargs)

        monkeypatch.setattr(
            device_catalog_route,
            "register_device",
            fake_register,
        )

        response = self._client().post(
            "/api/device-catalog/devices",
            json={
                "brand": "Vivo",
                "model": "S2 5G",
                "storage": "8GB + 128GB",
            },
        )

        assert response.status_code == 200
        assert captured["new_price_inr"] is None

    def test_add_device_returns_400_on_registry_error(self, monkeypatch):
        def failing_register(**kwargs):
            raise ValueError("Brand is required.")

        monkeypatch.setattr(
            device_catalog_route,
            "register_device",
            failing_register,
        )

        response = self._client().post(
            "/api/device-catalog/devices",
            json={
                "brand": "",
                "model": "",
                "storage": "",
            },
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "Brand is required."

    def test_add_device_validation_error(self):
        response = self._client().post(
            "/api/device-catalog/devices",
            json={
                "brand": "Vivo",
                "storage": "8GB + 128GB",
            },
        )

        assert response.status_code == 422
        assert "model" in response.json()["detail"][0]["loc"]

    def test_paginate(self):
        items = list(range(5))

        page = device_catalog_route._paginate(items, 1, 2)

        assert page["items"] == [0, 1]
        assert page["pagination"] == {
            "page": 1,
            "page_size": 2,
            "total": 5,
            "total_pages": 3,
            "has_next": True,
            "has_previous": False,
        }

        last = device_catalog_route._paginate(items, 3, 2)

        assert last["items"] == [4]
        assert last["pagination"]["has_next"] is False
        assert last["pagination"]["has_previous"] is True

    def _recent_client(self):
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
        app.include_router(device_catalog_route.router)
        app.dependency_overrides[get_db] = _get_test_db
        return TestClient(app), engine

    def test_recent_devices_empty(self):
        client, _ = self._recent_client()

        response = client.get(
            "/api/device-catalog/devices/recent"
        )

        assert response.status_code == 200
        assert response.json() == {"items": []}

    def test_recent_devices_lists_custom_rows(self):
        from app.models.price_cache import PriceCache

        client, engine = self._recent_client()

        db = Session(engine)
        db.add(
            PriceCache(
                cache_key="vivo|s2 5g|8gb + 128gb",
                brand="Vivo",
                model="S2 5G",
                storage="8GB + 128GB",
                exists="True",
                matched_model="S2 5G",
                valid_variants="[]",
                new_price_inr=24000,
                used_resale_price_inr=24000,
                price_source="custom",
                confidence="low",
                notes="Manually added device with ML-estimated price.",
                fetched_at="2026-09-05T10:00:00",
            )
        )
        db.add(
            PriceCache(
                cache_key="apple|iphone 17|8gb + 256gb",
                brand="Apple",
                model="iPhone 17",
                storage="8GB + 256GB",
                exists="True",
                matched_model="iPhone 17",
                valid_variants="[]",
                new_price_inr=99000,
                used_resale_price_inr=99000,
                price_source="custom",
                confidence="low",
                notes="Manually added device with ML-estimated price.",
                fetched_at="2026-09-05T11:30:00",
            )
        )
        db.commit()
        db.close()

        response = client.get(
            "/api/device-catalog/devices/recent?limit=10"
        )

        assert response.status_code == 200

        items = response.json()["items"]

        assert len(items) == 2

        # Newest first.
        assert items[0]["brand"] == "Apple"
        assert items[0]["model"] == "iPhone 17"
        assert items[0]["storage"] == "8GB + 256GB"
        assert items[0]["price_inr"] == 99000
        assert items[0]["added_at"] == "2026-09-05T11:30:00"

        assert items[1]["brand"] == "Vivo"
        assert items[1]["model"] == "S2 5G"
        assert items[1]["price_inr"] == 24000


class TestInspectionFlow:
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
        app.include_router(inspection_route.router)
        app.dependency_overrides[get_db] = _get_test_db
        return TestClient(app)

    def _fake_valuation(self, **kwargs):
        return {
            "market_price": 24000,
            "resale_price": 18000,
            "exchange_price": 15000,
            "new_price_inr": 24000,
            "price_source": "ml score",
            "condition_score": 82,
            "condition_grade": "A",
            "device": {
                "brand": "Vivo",
                "model": "S2 5G",
                "storage": "8GB + 128GB",
            },
            "model_source": "ml",
            "valuation_type": "quick_value",
        }

    def test_create_and_value_inspection(self, monkeypatch):
        monkeypatch.setattr(
            inspection_route,
            "calculate_valuation",
            self._fake_valuation,
        )

        client = self._client()

        created = client.post(
            "/api/inspections",
            json={
                "brand": "Vivo",
                "model": "S2 5G",
                "storage": "8GB + 128GB",
                "inspection_type": "quick_value",
            },
        )

        assert created.status_code == 200

        code = created.json()["inspection_code"]
        assert code.startswith("INS-")
        assert created.json()["status"] == "created"

        valued = client.post(
            f"/api/inspections/{code}/answers",
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

        assert valued.status_code == 200

        data = valued.json()

        assert data["inspection_code"] == code
        assert data["market_price"] == 24000
        assert data["resale_price"] == 18000
        assert data["exchange_price"] == 15000
        assert data["condition_grade"] == "A"
        assert data["device"] == {
            "brand": "Vivo",
            "model": "S2 5G",
            "storage": "8GB + 128GB",
        }

    def test_answers_unknown_code_returns_404(self, monkeypatch):
        monkeypatch.setattr(
            inspection_route,
            "calculate_valuation",
            self._fake_valuation,
        )

        response = self._client().post(
            "/api/inspections/INS-1999-NOPE/answers",
            json={"answers": []},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Inspection not found"


class TestInspectionLinkFlow:
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
        app.include_router(inspection_route.router)
        app.dependency_overrides[get_db] = _get_test_db
        return TestClient(app)

    def _create(self, client, inspection_type="full_inspection"):
        created = client.post(
            "/api/inspections",
            json={
                "brand": "Vivo",
                "model": "Y200e 5G",
                "storage": "8GB + 128GB",
                "inspection_type": inspection_type,
            },
        )

        assert created.status_code == 200

        data = created.json()

        assert len(data["link_code"]) == 6
        assert data["link_code"].isdigit()

        return data

    def test_create_returns_link_code(self):
        self._create(self._client())

    def test_status_flow(self):
        client = self._client()

        created = self._create(client)

        status = client.get(
            f"/api/inspections/{created['inspection_code']}"
        )

        assert status.status_code == 200

        data = status.json()

        assert data["link_code"] == created["link_code"]
        assert data["photos_complete"] is False
        assert data["photos_captured"] == 0
        assert data["diagnostics_complete"] is False
        assert data["working"] is None

    def test_status_unknown_returns_404(self):
        response = self._client().get(
            "/api/inspections/INS-1999-NOPE"
        )

        assert response.status_code == 404

    def test_link_returns_need_photos(self):
        client = self._client()

        created = self._create(client)

        linked = client.post(
            "/api/inspections/link",
            json={"link_code": created["link_code"]},
        )

        assert linked.status_code == 200

        data = linked.json()

        assert data["inspection_code"] == created["inspection_code"]
        assert data["need"] == "photos"
        assert data["brand"] == "Vivo"
        assert data["storage"] == "8GB + 128GB"

    def test_link_unknown_code_returns_404(self):
        response = self._client().post(
            "/api/inspections/link",
            json={"link_code": "999999"},
        )

        assert response.status_code == 404

    def test_diagnostics_submit_and_status(self):
        client = self._client()

        created = self._create(client)

        code = created["inspection_code"]

        submitted = client.post(
            f"/api/inspections/{code}/diagnostics",
            json={
                "working": "yes",
                "diagnostics_score": 78.0,
                "diagnostics_report": {
                    "healthScore": 78,
                    "finalGrade": "Good",
                    "sensorResults": {"camera": "passed"},
                },
            },
        )

        assert submitted.status_code == 200
        assert submitted.json()["accepted"] is True
        assert submitted.json()["working"] == "yes"
        assert submitted.json()["diagnostics_score"] == 78.0

        status = client.get(f"/api/inspections/{code}")

        assert status.json()["diagnostics_complete"] is True
        assert status.json()["working"] == "yes"
        assert status.json()["diagnostics_score"] == 78.0

    def test_link_returns_diagnostics_after_photos_only(self):
        client = self._client()

        created = self._create(client)

        code = created["inspection_code"]

        client.post(
            f"/api/inspections/{code}/diagnostics",
            json={
                "working": "no",
                "diagnostics_score": None,
            },
        )

        linked = client.post(
            "/api/inspections/link",
            json={"link_code": created["link_code"]},
        )

        # Photos are still pending, so the code still routes there.
        assert linked.json()["need"] == "photos"


class TestCompleteValuation:
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
        app.include_router(inspection_route.router)
        app.include_router(photo_analysis_route.router)
        app.dependency_overrides[get_db] = _get_test_db
        return TestClient(app)

    def test_complete_valuation_requires_diagnostics(
        self, monkeypatch
    ):
        client = self._client()

        created = client.post(
            "/api/inspections",
            json={
                "brand": "Vivo",
                "model": "Y200e 5G",
                "storage": "8GB + 128GB",
            },
        ).json()

        response = client.post(
            f"/api/inspections/{created['inspection_code']}/complete-valuate",
            json={"answers": [{"question_key": "screen", "answer_value": "good"}]},
        )

        assert response.status_code == 422

    def test_complete_valuation_happy_path(self, monkeypatch):
        client = self._client()

        created = client.post(
            "/api/inspections",
            json={
                "brand": "Vivo",
                "model": "Y200e 5G",
                "storage": "8GB + 128GB",
                "inspection_type": "full_inspection",
            },
        ).json()

        code = created["inspection_code"]

        client.post(
            f"/api/inspections/{code}/diagnostics",
            json={
                "working": "yes",
                "diagnostics_score": 82.0,
                "diagnostics_report": {
                    "healthScore": 82,
                    "finalGrade": "Good",
                },
            },
        )

        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda inspection_code, db: {
                "overall_photo_quality": 70,
                "physical_condition_ai": {
                    "effective_condition_score": 64,
                    "condition_score": 64,
                },
                "photos": [],
            },
        )

        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            lambda device: (13500, 20999, "ml score"),
        )

        response = client.post(
            f"/api/inspections/{code}/complete-valuate",
            json={
                "answers": [
                    {"question_key": "screen", "answer_value": "good"},
                    {"question_key": "battery", "answer_value": "good"},
                ]
            },
        )

        assert response.status_code == 200

        data = response.json()

        assert data["valuation_type"] == "Complete Full Inspection"
        assert data["inspection_code"] == code
        assert data["market_price"] == 13500
        assert data["resale_price"] > 0
        assert data["exchange_price"] > 0
        assert data["questionnaire_score"] >= 0
        assert data["ai_condition_score"] == 64
        assert data["diagnostics"]["working"] == "yes"
        assert data["diagnostics"]["diagnostics_score"] == 82.0
        assert data["diagnostics"]["report"]["finalGrade"] == "Good"
        assert "condition_grade" in data


class TestMlPredict:
    def _client(self):
        app = FastAPI()
        app.include_router(ml_valuation_route.router)
        return TestClient(app)

    def test_predict_success(self, monkeypatch):
        monkeypatch.setattr(
            ml_valuation_route,
            "calculate_ml_valuation",
            lambda device_data, condition_score: {
                "estimated_price_inr": 23500,
                "used_resale_price_inr": 17625,
                "condition_score": condition_score,
            },
        )

        response = self._client().post(
            "/ml/predict",
            json={
                "smartphone_brand": "Vivo",
                "model": "S2 5G",
                "condition_score": 85.0,
            },
        )

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["valuation"]["estimated_price_inr"] == 23500
        assert response.json()["valuation"]["condition_score"] == 85.0

    def test_predict_returns_500_on_model_error(self, monkeypatch):
        def exploding(device_data, condition_score):
            raise RuntimeError("Model not loaded")

        monkeypatch.setattr(
            ml_valuation_route,
            "calculate_ml_valuation",
            exploding,
        )

        response = self._client().post(
            "/ml/predict",
            json={
                "smartphone_brand": "Vivo",
                "model": "S2 5G",
            },
        )

        assert response.status_code == 500
        assert "Model not loaded" in response.json()["detail"]


class TestHealth:
    def _client(self):
        app = FastAPI()
        app.include_router(health_route.router)
        return TestClient(app)

    def test_health_shape(self):
        response = self._client().get("/api/health")

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert isinstance(data["model_loaded"], bool)
        assert isinstance(data["dataset_rows"], int)
        assert isinstance(data["gemini_configured"], bool)
        assert "database" in data


class TestTwoPhoneCoordination:
    """
    Full end-to-end test of the two-phone coordination flow:

    1. Primary creates inspection.
    2. Secondary joins via link code  → need == "photos".
    3. Secondary uploads 6 photos.
    4. Secondary re-joins              → need == "diagnostics".
    5. Secondary submits diagnostics.
    6. Secondary re-joins              → need == "complete".
    7. Primary polls status            → valuable == True.
    8. Primary submits answers         → combined valuation returned.
    """

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
        app.include_router(inspection_route.router)
        app.include_router(photos_route.router)
        app.include_router(photo_analysis_route.router)
        app.dependency_overrides[get_db] = _get_test_db
        return TestClient(app)

    def _create(self, client):
        resp = client.post(
            "/api/inspections",
            json={
                "brand": "Vivo",
                "model": "Y200e 5G",
                "storage": "8GB + 128GB",
                "inspection_type": "full_inspection",
            },
        )
        assert resp.status_code == 200
        return resp.json()

    def _upload_photos(self, client, code, monkeypatch):
        """Upload 6 dummy JPEG photos, stubbing supabase storage."""

        monkeypatch.setattr(
            photos_route,
            "supabase",
            type("_S", (), {
                "storage": type("_ST", (), {
                    "from_": lambda self, bucket: type(
                        "_B", (), {"upload": lambda self, *a, **kw: None}
                    )()
                })()
            })(),
        )

        for photo_type in ("front", "back", "left", "right", "top", "bottom"):
            resp = client.post(
                f"/api/inspections/{code}/photos",
                params={"photo_type": photo_type},
                files={"file": ("test.jpg", b"\xff\xd8\xff\xe0fake-jpeg", "image/jpeg")},
            )
            assert resp.status_code == 200

    def test_full_two_phone_flow(self, monkeypatch):
        client = self._client()

        # Step 1: Primary creates inspection
        created = self._create(client)
        code = created["inspection_code"]
        link = created["link_code"]
        assert len(link) == 6

        # Step 2: Secondary links → need == "photos"
        resp = client.post(
            "/api/inspections/link",
            json={"link_code": link},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["need"] == "photos"
        assert data["inspection_code"] == code

        # Step 3: Secondary uploads 6 photos
        self._upload_photos(client, code, monkeypatch)

        # Verify status shows photos complete
        status = client.get(f"/api/inspections/{code}").json()
        assert status["photos_captured"] == 6
        assert status["photos_complete"] is True

        # Step 4: Secondary re-links → need == "diagnostics"
        resp = client.post(
            "/api/inspections/link",
            json={"link_code": link},
        )
        assert resp.json()["need"] == "diagnostics"

        # Step 5: Secondary submits diagnostics
        resp = client.post(
            f"/api/inspections/{code}/diagnostics",
            json={
                "working": "yes",
                "diagnostics_score": 85.0,
                "diagnostics_report": {
                    "finalScore": 85,
                    "finalGrade": "Good",
                    "sensorResults": {"camera": "passed", "touch": "passed"},
                },
            },
        )
        assert resp.status_code == 200
        assert resp.json()["working"] == "yes"

        # Step 6: Secondary re-links → need == "complete"
        resp = client.post(
            "/api/inspections/link",
            json={"link_code": link},
        )
        assert resp.json()["need"] == "complete"

        # Step 7: Primary polls → valuable == True
        status = client.get(f"/api/inspections/{code}").json()
        assert status["photos_complete"] is True
        assert status["diagnostics_complete"] is True
        assert status["valuable"] is True

        # Step 8: Primary submits answers → full valuation
        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda inspection_code, db: {
                "overall_photo_quality": 72,
                "physical_condition_ai": {
                    "effective_condition_score": 68,
                    "condition_score": 68,
                },
                "photos": [],
            },
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            lambda device: (14000, 21999, "ml dataset"),
        )

        resp = client.post(
            f"/api/inspections/{code}/complete-valuate",
            json={
                "answers": [
                    {"question_key": "screen_condition", "answer_value": "minor_scratches"},
                    {"question_key": "battery_condition", "answer_value": "good"},
                    {"question_key": "functionality", "answer_value": "yes"},
                ]
            },
        )
        assert resp.status_code == 200

        result = resp.json()
        assert result["inspection_code"] == code
        assert result["valuation_type"] == "Complete Full Inspection"
        assert result["market_price"] == 14000
        assert result["resale_price"] > 0
        assert result["exchange_price"] > 0
        assert result["ai_condition_score"] == 68
        assert result["questionnaire_score"] > 0
        assert result["diagnostics"]["working"] == "yes"
        assert result["diagnostics"]["diagnostics_score"] == 85.0

    def test_diagnostic_score_zero_when_not_working(self, monkeypatch):
        """Secondary reports phone broken → diagnostics score 0, still valued."""
        client = self._client()

        created = self._create(client)
        code = created["inspection_code"]
        link = created["link_code"]

        self._upload_photos(client, code, monkeypatch)

        resp = client.post(
            f"/api/inspections/{code}/diagnostics",
            json={
                "working": "no",
                "diagnostics_score": 0,
                "diagnostics_report": {"working": "no"},
            },
        )
        assert resp.status_code == 200

        monkeypatch.setattr(
            photo_analysis_route,
            "analyze_photos",
            lambda inspection_code, db: {
                "overall_photo_quality": 60,
                "physical_condition_ai": {
                    "effective_condition_score": 55,
                    "condition_score": 55,
                },
                "photos": [],
            },
        )
        monkeypatch.setattr(
            photo_analysis_route,
            "get_market_price_for_device",
            lambda device: (10000, 18000, "dataset"),
        )

        resp = client.post(
            f"/api/inspections/{code}/complete-valuate",
            json={"answers": [{"question_key": "screen_condition", "answer_value": "cracked"}]},
        )
        assert resp.status_code == 200

        result = resp.json()
        assert result["diagnostics"]["working"] == "no"
        assert result["diagnostics"]["diagnostics_score"] == 0
        assert result["resale_price"] > 0