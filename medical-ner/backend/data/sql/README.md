# Database SQL Dumps

## 📦 Available Dumps

### `medical_ner_data.sql` (570 MB)

**Full database export** containing:
- **1,240 articles** - Crawled from medical websites
- **28,653 sentences** - Processed and segmented
- **5 corrections** - Human-annotated samples from Phase 2

**Last updated**: 2026-04-04

---

## 🚀 How to Import Data

### Prerequisites

1. PostgreSQL 14+ installed
2. Database created:
   ```bash
   createdb -U postgres medical_ner
   ```

3. User created with permissions:
   ```sql
   CREATE USER medical_user WITH PASSWORD 'medical_pass_2024';
   GRANT ALL PRIVILEGES ON DATABASE medical_ner TO medical_user;
   ```

### Import Steps

#### Option 1: Import with psql (Recommended)

```bash
# Navigate to this directory
cd medical-ner/backend/data/sql

# Set password environment variable
export PGPASSWORD='medical_pass_2024'  # Linux/Mac
# OR
$env:PGPASSWORD='medical_pass_2024'    # Windows PowerShell

# Import data (takes ~2-5 minutes)
psql -U medical_user -h localhost -d medical_ner -f medical_ner_data.sql

# Verify import
psql -U medical_user -h localhost -d medical_ner -c "
SELECT 
    'articles' as table_name, COUNT(*) as rows FROM articles
UNION ALL
SELECT 'sentences', COUNT(*) FROM sentences
UNION ALL
SELECT 'corrections', COUNT(*) FROM corrections;
"
```

Expected output:
```
 table_name  | rows
-------------+-------
 articles    | 1240
 sentences   | 28653
 corrections |    5
```

#### Option 2: Import with pgAdmin

1. Open pgAdmin
2. Connect to your PostgreSQL server
3. Select `medical_ner` database
4. Right-click → **Restore**
5. Choose `medical_ner_data.sql`
6. Click **Restore**

---

## ⚠️ Important Notes

### 1. Schema Must Exist First

Before importing data, ensure database tables are created:

```bash
# Run migrations (from backend directory)
cd ../../
alembic upgrade head
```

This creates the schema:
- `articles` table
- `sentences` table
- `entities` table
- `knowledge_map` table
- `corrections` table (Phase 2)

### 2. Data Only (No Schema)

The dump file contains **INSERT statements only**, not CREATE TABLE statements.

If you get errors like `table "articles" does not exist`, run migrations first.

### 3. Large File Warning

- File size: **570 MB**
- Import time: **2-5 minutes** depending on hardware
- Disk space needed: **~1.5 GB** after import (with indexes)

### 4. Clean Import

If you want to re-import:

```sql
-- Delete existing data
TRUNCATE articles, sentences, entities, knowledge_map, corrections CASCADE;

-- Then re-import
\i medical_ner_data.sql
```

---

## 📊 Data Sources

Articles crawled from:
- **vinmec.com** - 600+ articles
- **suckhoedoisong.vn** - 400+ articles
- **hellobacsi.com** - 200+ articles
- Other medical websites

**Topics covered**:
- Diseases and conditions
- Medications and treatments
- Medical tests and procedures
- Symptoms and diagnosis
- Body parts and anatomy

---

## 🔄 Updating the Dump

To create a new dump after crawling more data:

```bash
# Set password
export PGPASSWORD='medical_pass_2024'

# Create new dump
pg_dump -U medical_user -h localhost -d medical_ner \
  -F p --data-only --inserts \
  -f medical_ner_data.sql

# Check size
ls -lh medical_ner_data.sql
```

---

## 🆘 Troubleshooting

### Error: "role medical_user does not exist"

Create the user:
```sql
CREATE USER medical_user WITH PASSWORD 'medical_pass_2024';
GRANT ALL PRIVILEGES ON DATABASE medical_ner TO medical_user;
```

### Error: "database medical_ner does not exist"

Create the database:
```bash
createdb -U postgres medical_ner
```

### Error: "relation articles does not exist"

Run migrations first:
```bash
cd ../..
alembic upgrade head
```

### Import is slow

This is normal for 570 MB of data. Progress indicators:
- ~30% at 1 minute
- ~60% at 2 minutes  
- ~100% at 3-5 minutes

---

## 📈 Statistics After Import

Run this query to verify:

```sql
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
    (SELECT COUNT(*) FROM articles) as articles_count,
    (SELECT COUNT(*) FROM sentences) as sentences_count,
    (SELECT COUNT(*) FROM corrections) as corrections_count
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

**Note**: This dump is for development/testing. For production, use proper backup strategies with `pg_dump` in custom format (`-Fc`) for better compression and parallel restore.
