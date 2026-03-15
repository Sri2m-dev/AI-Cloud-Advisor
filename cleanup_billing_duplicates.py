from database.db import cleanup_billing_data_duplicates, get_billing_duplicate_count


def main():
    before = get_billing_duplicate_count()
    removed = cleanup_billing_data_duplicates()
    after = get_billing_duplicate_count()
    print(f"Duplicate billing rows before cleanup: {before}")
    print(f"Duplicate billing rows removed: {removed}")
    print(f"Duplicate billing rows after cleanup: {after}")


if __name__ == "__main__":
    main()