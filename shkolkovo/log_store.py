import csv
import datetime
import os


class CsvProcessLogStore:
    FIELDNAMES = ["date", "ts", "id", "name", "hints", "ok"]

    def __init__(self, base_dir: str | None = None):
        self.base_dir = base_dir or os.path.join(os.path.expanduser("~"), ".shkolkovo_logs")
        os.makedirs(self.base_dir, exist_ok=True)

    def path_for_day(self, day: str | None = None) -> str:
        day = day or datetime.date.today().isoformat()
        return os.path.join(self.base_dir, f"process_log_{day}.csv")

    def load_for_day(self, day: str | None = None) -> list[dict]:
        path = self.path_for_day(day)
        if not os.path.exists(path):
            return []
        with open(path, newline="", encoding="utf-8-sig") as file:
            rows = []
            for row in csv.DictReader(file):
                if not row:
                    continue
                rows.append(
                    {
                        "date": row.get("date", ""),
                        "ts": row.get("ts", ""),
                        "id": row.get("id", ""),
                        "name": row.get("name", ""),
                        "hints": int(row.get("hints", 0) or 0),
                        "ok": str(row.get("ok", "")).strip().lower() in {"1", "true", "yes", "да"},
                    }
                )
        return rows

    def append(self, entry: dict):
        path = self.path_for_day(entry.get("date"))
        exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=self.FIELDNAMES)
            if not exists:
                writer.writeheader()
            writer.writerow(
                {
                    "date": entry.get("date", ""),
                    "ts": entry.get("ts", ""),
                    "id": entry.get("id", ""),
                    "name": entry.get("name", ""),
                    "hints": entry.get("hints", 0),
                    "ok": 1 if entry.get("ok") else 0,
                }
            )
