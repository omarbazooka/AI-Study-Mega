import sys
import os
import psycopg2

def load_dotenv():
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Strip quotes if present
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                os.environ.setdefault(k, v)

def main():
    print("=" * 60)
    print("        SUPABASE SECURE POSTGRESQL MIGRATION RUNNER")
    print("=" * 60)

    # Load environment variables
    load_dotenv()

    # Retrieve connection properties
    database_url = os.environ.get("DATABASE_URL")
    db_password = os.environ.get("SUPABASE_DB_PASSWORD")
    supabase_url = os.environ.get("SUPABASE_URL")
    
    # Deriving properties if DATABASE_URL is not present
    conn_params_list = []
    if database_url:
        print("Using connection configuration from: DATABASE_URL")
        conn_params_list.append({"dsn": database_url})
    else:
        print("Building connection parameters from environment...")
        if not supabase_url:
            print("Error: SUPABASE_URL or DATABASE_URL must be specified in the environment.")
            sys.exit(1)
            
        project_ref = supabase_url.replace("https://", "").replace("http://", "").split(".")[0]
        
        # Option 1: Direct host connection on 5432
        direct_host = os.environ.get("SUPABASE_DB_HOST", f"db.{project_ref}.supabase.co")
        if db_password:
            conn_params_list.append({
                "host": direct_host,
                "port": 5432,
                "user": "postgres",
                "password": db_password,
                "database": "postgres",
                "connect_timeout": 3
            })
            
        # Option 2: Pooler connections on port 6543 across regions
        POOLER_REGIONS = [
            "us-east-1", "us-east-2", "eu-central-1", "eu-west-1", "eu-west-2",
            "us-west-1", "us-west-2", "ap-southeast-1", "ap-northeast-1", "ap-southeast-2"
        ]
        for region in POOLER_REGIONS:
            conn_params_list.append({
                "host": f"aws-0-{region}.pooler.supabase.com",
                "port": 6543,
                "user": f"postgres.{project_ref}",
                "password": db_password,
                "database": "postgres",
                "connect_timeout": 3
            })

    # Find migration script — accepts optional CLI arg, defaults to 003
    migration_filename = sys.argv[1] if len(sys.argv) > 1 else "003_update_embedding_dimension.sql"
    migration_file = os.path.abspath(os.path.join(
        os.path.dirname(__file__), f"../app/db/migrations/{migration_filename}"
    ))

    if not os.path.exists(migration_file):
        print(f"Error: Migration file not found at: {migration_file}")
        sys.exit(1)

    print(f"Reading SQL script: {os.path.basename(migration_file)}")
    with open(migration_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    print("Connecting to Supabase PostgreSQL...")
    conn = None
    for conn_params in conn_params_list:
        try:
            h = conn_params.get("host", "DATABASE_URL")
            p = conn_params.get("port", "")
            print(f"Attempting to connect to {h}:{p}...")
            conn = psycopg2.connect(**conn_params)
            conn.autocommit = False
            print(f"Connection established successfully to {h}!")
            break
        except Exception as e:
            continue

    if not conn:
        print("Connection failed: All connection methods exhausted.")
        sys.exit(1)

    print("Executing database migration inside a secure transaction...")
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql_content)
        # Commit the transaction on success
        conn.commit()
        print("SUCCESS: Migration applied and committed successfully!")
    except Exception as e:
        # Rollback the transaction on failure
        conn.rollback()
        print("FAILURE: Migration failed. Rollback executed.")
        sys.stderr.write(f"Execution Error: {str(e)}\n")
        conn.close()
        sys.exit(1)

    conn.close()
    print("=" * 60)

if __name__ == "__main__":
    main()
