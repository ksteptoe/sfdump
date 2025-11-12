from sf_auth import run_salesforce_query

if __name__ == "__main__":
    data = run_salesforce_query("SELECT Id, Name FROM Account LIMIT 3")
    for rec in data.get("records", []):
        print(rec["Id"], rec["Name"])
