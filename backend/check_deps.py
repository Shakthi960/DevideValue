import sys
print(f"Python: {sys.version}")

try:
    import fastapi
    print(f"FastAPI: {fastapi.__version__}")
except ImportError:
    print("FastAPI: NOT INSTALLED")

try:
    import sqlalchemy
    print(f"SQLAlchemy: {sqlalchemy.__version__}")
except ImportError:
    print("SQLAlchemy: NOT INSTALLED")

try:
    import sklearn
    print(f"scikit-learn: {sklearn.__version__}")
except ImportError:
    print("scikit-learn: NOT INSTALLED")

try:
    import google.genai
    print("google-genai: OK")
except ImportError:
    print("google-genai: NOT INSTALLED")

try:
    import chromadb
    print(f"chromadb: {chromadb.__version__}")
except ImportError:
    print("chromadb: NOT INSTALLED")

try:
    import sentence_transformers
    print(f"sentence-transformers: {sentence_transformers.__version__}")
except ImportError:
    print("sentence-transformers: NOT INSTALLED")

try:
    import cv2
    print(f"opencv: {cv2.__version__}")
except ImportError:
    print("opencv: NOT INSTALLED")

try:
    import ultralytics
    print(f"ultralytics: {ultralytics.__version__}")
except ImportError:
    print("ultralytics: NOT INSTALLED")

try:
    import joblib
    print("joblib: OK")
except ImportError:
    print("joblib: NOT INSTALLED")
