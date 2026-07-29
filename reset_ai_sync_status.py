from app.repository.applicant_repository import ApplicantRepository


def main():
    repo = ApplicantRepository()

    result = repo.collection.update_many(
        {
            "AI_SYNC_STATUS": "COMPLETED"
        },
        {
            "$set": {
                "AI_SYNC_STATUS": "PENDING"
            }
        }
    )

    print(f"Reset {result.modified_count} applicants to PENDING")


if __name__ == "__main__":
    main()