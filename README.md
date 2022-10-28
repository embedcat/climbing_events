# climbing-events
Сервис для ввода и подсчёта результатов скалолазных соревнований

### Database dump:
- Dump on remote:
`pg_dump -h localhost -U <db_user> -Fc <db_name> > dump.backup`
- Copy to local:
`scp user@host:/path/to/dbdump.backup .`
- Create db:
  - `sudo -u postgres psql`
  - `CREATE DATABASE <db> WITH ENCODING='UTF8' LC_CTYPE='en_US.UTF-8' LC_COLLATE='en_US.UTF-8' TEMPLATE=template0;`
  - `CREATE USER <db_user> WITH PASSWORD '<db_password>';`
  - `GRANT ALL PRIVILEGES ON DATABASE <db> TO <db_user>;`
- Restore database
    - in pgAdmin: create user and db, restore
    - in cli: `pg_restore -h localhost -p 5432 -U <db_user> -d <db> -v dump.backup `
