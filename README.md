# climbing-events
Сервис для ввода и подсчёта результатов скалолазных соревнований

### Database dump:
- Dump on remote:
`pg_dump -h localhost -U [username] -Fc [db_name] > dbdump.backup`
- Copy to local:
`scp user@host:/root/climbing_events/dbdump.backup ./`
- Restore database: in pgAdmin: create user and db, restore