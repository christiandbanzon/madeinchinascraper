from fastapi import FastAPI
from pydantic import BaseModel
import time
from typing import List
import asyncio
from pathlib import Path
import glob

from src.scraper import MadeInChinaScraper
from src.data_manager import DataManager
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response, FileResponse, JSONResponse
import threading


class ScrapeRequest(BaseModel):
    keyword: str
    max_pages: int = 5
    target_count: int = 100
    use_selenium: bool = False


class ScrapeResponse(BaseModel):
    keyword: str
    total_listings: int
    elapsed_seconds: float
    pages_visited: int


app = FastAPI(title="Made-in-China Scraper API")

# Metrics
SCRAPE_REQUESTS = Counter("scrape_requests_total", "Number of scrape requests", ["keyword"])
SCRAPE_ITEMS = Counter("scrape_items_total", "Total items scraped", ["keyword"])
SCRAPE_DURATION = Histogram("scrape_duration_seconds", "Scrape duration in seconds", ["keyword"])


@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

# Clean root endpoint (for UI parity)
@app.get("/")
def root():
    return {"message": "Root"}

# Available domains (placeholder)
@app.get("/domains")
def domains():
    return {"domains": ["made-in-china"]}

# Rate-limit info (placeholder/stub)
@app.get("/rate-limit")
def rate_limit():
    return {"limit": 60, "remaining": 60, "window_seconds": 60}

def _run_scrape_sync(req: ScrapeRequest) -> tuple[int, int]:
    scraper = MadeInChinaScraper(use_selenium=req.use_selenium)
    data_manager = DataManager()
    try:
        listings_total = 0
        pages = 0
        for _ in range(1, req.max_pages + 1):
            pages += 1
            result = scraper.search_products(req.keyword, max_pages=1)
            listings_total += len(result.listings)
            data_manager.save_search_result(result)
            if listings_total >= req.target_count:
                break
        return listings_total, pages
    finally:
        scraper.close()


# NOTE: /scrape endpoint removed per requirements; only /scan is exposed


# --- Scan flow matching desired endpoints ---
SCANS: dict[str, dict] = {}
SCAN_LOCK = threading.Lock()


class ScanRequest(BaseModel):
    keywords: List[str]
    max_pages: int = 5
    target_count: int = 100
    use_selenium: bool = False


@app.post("/scan")
def start_scan(req: ScanRequest):
    scan_id = f"scan-{int(time.time()*1000)}"
    with SCAN_LOCK:
        SCANS[scan_id] = {"status": "queued", "results": None}

    def worker():
        try:
            # mark as running
            with SCAN_LOCK:
                if scan_id in SCANS:
                    SCANS[scan_id]["status"] = "running"
            total = 0
            pages_total = 0
            data_manager = DataManager()
            for kw in req.keywords:
                # Reuse sync helper
                t, p = _run_scrape_sync(ScrapeRequest(keyword=kw, max_pages=req.max_pages, target_count=req.target_count, use_selenium=req.use_selenium))
                total += t
                pages_total += p
            # Find latest export files for first keyword as representative
            json_files = sorted(glob.glob(str(Path(data_manager.data_dir) / f"search_{req.keywords[0]}_*.json")))
            csv_files = sorted(glob.glob(str(Path(data_manager.data_dir) / f"search_{req.keywords[0]}_*.csv")))
            with SCAN_LOCK:
                SCANS[scan_id] = {
                    "status": "done",
                    "summary": {"total_listings": total, "pages_visited": pages_total},
                    "json_path": json_files[-1] if json_files else None,
                    "csv_path": csv_files[-1] if csv_files else None,
                }
        except Exception as e:
            with SCAN_LOCK:
                SCANS[scan_id] = {"status": "error", "error": str(e)}

    threading.Thread(target=worker, daemon=True).start()
    return {"scan_id": scan_id}


@app.get("/scan/{scan_id}/status")
def scan_status(scan_id: str):
    with SCAN_LOCK:
        return SCANS.get(scan_id, {"status": "not_found"})


@app.get("/scan/{scan_id}/results")
def scan_results(scan_id: str):
    with SCAN_LOCK:
        rec = SCANS.get(scan_id)
    if not rec:
        return JSONResponse({"status": "not_found"}, status_code=404)
    if rec.get("status") != "done" or not rec.get("json_path"):
        return JSONResponse({"status": rec.get("status", "unknown")}, status_code=202)
    p = rec["json_path"]
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return JSONResponse(content=__import__('json').load(f))
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)


@app.get("/scan/{scan_id}/results/csv")
def scan_results_csv(scan_id: str):
    with SCAN_LOCK:
        rec = SCANS.get(scan_id)
    if not rec:
        return JSONResponse({"status": "not_found"}, status_code=404)
    if rec.get("status") != "done" or not rec.get("csv_path"):
        return JSONResponse({"status": rec.get("status", "unknown")}, status_code=202)
    return FileResponse(rec["csv_path"], media_type="text/csv", filename=Path(rec["csv_path"]).name)

# Queue maintenance endpoints
@app.delete("/scan")
def clear_scans():
    with SCAN_LOCK:
        SCANS.clear()
    return {"status": "cleared"}

@app.delete("/scan/{scan_id}")
def clear_scan(scan_id: str):
    with SCAN_LOCK:
        existed = scan_id in SCANS
        if existed:
            del SCANS[scan_id]
    return {"status": "deleted" if existed else "not_found"}

# Simple in-process job queue
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()

@app.post("/jobs", status_code=202, include_in_schema=False)
def submit_job(req: ScrapeRequest):
    job_id = f"job-{int(time.time()*1000)}"
    with LOCK:
        JOBS[job_id] = {"status": "queued"}

    def worker():
        try:
            listings_total, pages = _run_scrape_sync(req)
            resp = ScrapeResponse(
                keyword=req.keyword,
                total_listings=listings_total,
                elapsed_seconds=0.0,
                pages_visited=pages,
            )
            with LOCK:
                JOBS[job_id] = {"status": "done", "result": resp.dict()}
        except Exception as e:
            with LOCK:
                JOBS[job_id] = {"status": "error", "error": str(e)}

    threading.Thread(target=worker, daemon=True).start()
    return {"job_id": job_id}

@app.get("/jobs/{job_id}", include_in_schema=False)
def get_job(job_id: str):
    with LOCK:
        return JOBS.get(job_id, {"status": "not_found"})

@app.delete("/jobs/{job_id}", include_in_schema=False)
def cancel_job(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            return {"status": "not_found"}
        job["status"] = "cancelling"
        JOBS[job_id] = job
    return {"status": "cancelling"}


