from fastapi import FastAPI
from pydantic import BaseModel
import time
from typing import List
import asyncio

from src.scraper import MadeInChinaScraper
from src.data_manager import DataManager
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response
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


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest):
    start = time.time()
    SCRAPE_REQUESTS.labels(req.keyword).inc()
    listings_total, pages = await asyncio.to_thread(_run_scrape_sync, req)
    elapsed = time.time() - start
    SCRAPE_ITEMS.labels(req.keyword).inc(listings_total)
    SCRAPE_DURATION.labels(req.keyword).observe(elapsed)
    return ScrapeResponse(
        keyword=req.keyword,
        total_listings=listings_total,
        elapsed_seconds=round(elapsed, 2),
        pages_visited=pages,
    )

# Simple in-process job queue
JOBS: dict[str, dict] = {}
LOCK = threading.Lock()

@app.post("/jobs", status_code=202)
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

@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    with LOCK:
        return JOBS.get(job_id, {"status": "not_found"})

@app.delete("/jobs/{job_id}")
def cancel_job(job_id: str):
    with LOCK:
        job = JOBS.get(job_id)
        if not job:
            return {"status": "not_found"}
        job["status"] = "cancelling"
        JOBS[job_id] = job
    return {"status": "cancelling"}


