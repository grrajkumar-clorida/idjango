-- Run once on LOCAL system MySQL (not VPS).
-- Replace YOUR_DB_PASSWORD with the same value as DATABASE_PASSWORD in idirect/.env
--
--   sudo mysql
--   source /absolute/path/to/idjango/_tips/local_mysql_setup.sql

CREATE DATABASE IF NOT EXISTS idjangoalgo
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'idjango_algogr8'@'localhost'
  IDENTIFIED BY 'YOUR_DB_PASSWORD';

GRANT ALL PRIVILEGES ON idjangoalgo.* TO 'idjango_algogr8'@'localhost';
FLUSH PRIVILEGES;
