import cloudinary
import cloudinary.uploader
import os
import shutil
from uuid import uuid4
from dotenv import load_dotenv

load_dotenv()

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)


def _cloudinary_env_ready() -> bool:
    return bool(
        os.getenv("CLOUDINARY_CLOUD_NAME")
        and os.getenv("CLOUDINARY_API_KEY")
        and os.getenv("CLOUDINARY_API_SECRET")
    )


def _use_cloudinary_for_cv() -> bool:
    """Opt-in: public PDF URLs on Cloudinary often return 401 until 'Allow delivery of PDF and ZIP' is enabled in Cloudinary Security."""
    flag = (os.getenv("USE_CLOUDINARY_CV") or "").strip().lower()
    return flag in ("1", "true", "yes") and _cloudinary_env_ready()


def upload_cv(file_path: str) -> str | None:
    try:
        response = cloudinary.uploader.upload(
            file_path,
            resource_type="raw",
            folder="hr_system/cvs",
            access_mode="public",
        )
        return response.get("secure_url")
    except Exception as e:
        print(f"Error uploading to Cloudinary: {e}")
        return None


def store_cv_and_get_url(temp_path: str) -> str | None:
    """
    Persist applicant CV and return a URL the browser can open.

    By default files are stored under uploads/cv and served via /static/cv/...
    Set USE_CLOUDINARY_CV=1 (and Cloudinary env vars) only after enabling PDF/ZIP
    public delivery in the Cloudinary console Security settings.
    """
    if _use_cloudinary_for_cv():
        url = upload_cv(temp_path)
        if url:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return url

    dest_dir = os.path.join("uploads", "cv")
    os.makedirs(dest_dir, exist_ok=True)
    dest_name = f"{uuid4().hex}.pdf"
    dest = os.path.join(dest_dir, dest_name)
    try:
        shutil.move(temp_path, dest)
    except OSError as e:
        print(f"Error saving CV locally: {e}")
        return None
    return f"/static/cv/{dest_name}"
