#!/usr/bin/env python3
from src.app import main as app_main
import argparse
import time
from src.scraper import MadeInChinaScraper


def benchmark():
    parser = argparse.ArgumentParser(description="Benchmark time to N results")
    parser.add_argument("keyword")
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--selenium", action="store_true")
    args = parser.parse_args()

    scraper = MadeInChinaScraper(use_selenium=args.selenium)
    total = 0
    pages = 0
    start = time.time()
    try:
        for _ in range(args.max_pages):
            pages += 1
            result = scraper.search_products(args.keyword, max_pages=1)
            total += len(result.listings)
            if total >= args.target:
                break
    finally:
        scraper.close()
    elapsed = time.time() - start
    print(f"keyword={args.keyword} target={args.target} total={total} pages={pages} elapsed_s={elapsed:.2f}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        sys.argv.pop(1)
        benchmark()
    else:
        app_main()

