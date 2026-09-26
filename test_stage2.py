"""
End-to-end Stage 2 integration test.
Runs with a live Redis and real video.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from backend.app.config import settings
from backend.app.database import init_db, SessionLocal
from backend.app.models.video_asset import VideoAsset
from backend.app.services.job_service import JobService
from backend.app.services.queue_service import is_redis_available
from backend.app.worker.tasks import process_job

def main():
    settings.ensure_dirs()
    init_db()

    # Check Redis
    if not is_redis_available():
        print("ERROR: Redis not available. Start redis-server first.")
        sys.exit(1)
    print("Redis: OK")

    # Load test video
    video_path = Path("instagram_reel.mp4")
    if not video_path.exists():
        print("ERROR: instagram_reel.mp4 not found")
        sys.exit(1)

    db = SessionLocal()
    try:
        # Create a source asset
        asset = VideoAsset(
            id=str(uuid.uuid4()),
            source="instagram",
            file_path=str(video_path.resolve()),
            original_filename=video_path.name,
            mime_type="video/mp4",
        )
        db.add(asset)
        db.commit()
        asset_id = asset.id
        print(f"Created source asset: {asset_id}")

        # Create job
        job = JobService.create_job(db, asset_id, "crop")
        job_id = job.id
        print(f"Created job: {job_id} (status: {job.status})")
        db.close()

        # Run worker task directly (simulates worker processing)
        print("Running worker task (crop)...")
        result = process_job(job_id)
        print(f"Result: {result}")
        assert result["status"] == "completed"

        # Verify output
        db2 = SessionLocal()
        try:
            out = db2.query(VideoAsset).filter(VideoAsset.id == result["output_asset_id"]).first()
            assert out is not None
            assert out.width == 1080
            assert out.height == 1920
            assert out.conversion_mode == "crop"
            assert Path(out.file_path).exists()
            print(f"Output asset: {out.id}")
            print(f"Dimensions: {out.width}x{out.height}")
            print(f"File: {out.file_path}")
            print(f"Size: {out.file_size} bytes")
        finally:
            db2.close()

        print("\nStage 2 end-to-end test PASSED")

    except Exception as e:
        db.close()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

