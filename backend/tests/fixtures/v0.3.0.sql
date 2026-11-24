BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('0002');
CREATE TABLE checkins (
	habit_id INTEGER NOT NULL, 
	local_date DATE NOT NULL, 
	done BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	last_op_id VARCHAR(64), 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (habit_id, local_date), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE
);
INSERT INTO "checkins" VALUES(1,'2026-11-23',1,1,'op-1','2026-11-23 19:00:00');
INSERT INTO "checkins" VALUES(1,'2026-11-24',0,2,'op-2','2026-11-24 07:00:00');
INSERT INTO "checkins" VALUES(2,'2026-11-18',1,1,NULL,'2026-11-18 06:30:00');
INSERT INTO "checkins" VALUES(3,'2026-11-22',1,1,NULL,'2026-11-22 18:00:00');
CREATE TABLE habit_schedules (
	id INTEGER NOT NULL, 
	habit_id INTEGER NOT NULL, 
	valid_from DATE NOT NULL, 
	weekdays INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_habit_schedule_weekdays CHECK (weekdays BETWEEN 0 AND 127), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE, 
	CONSTRAINT uq_habit_schedule_valid_from UNIQUE (habit_id, valid_from)
);
INSERT INTO "habit_schedules" VALUES(1,1,'2026-11-01',127);
INSERT INTO "habit_schedules" VALUES(2,2,'2026-11-01',21);
INSERT INTO "habit_schedules" VALUES(3,2,'2026-11-21',0);
INSERT INTO "habit_schedules" VALUES(4,3,'2026-11-02',96);
CREATE TABLE habits (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	cue VARCHAR(200), 
	sort_order INTEGER NOT NULL, 
	archived_on DATE, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "habits" VALUES(1,1,'Lesen','nach dem Frühstück',1,NULL,'2026-11-01 08:05:00');
INSERT INTO "habits" VALUES(2,1,'Laufen',NULL,2,'2026-11-20','2026-11-01 08:06:00');
INSERT INTO "habits" VALUES(3,2,'Gitarre',NULL,1,NULL,'2026-11-02 09:40:00');
CREATE TABLE shortcut_tokens (
	id INTEGER NOT NULL, 
	habit_id INTEGER NOT NULL, 
	label VARCHAR(80) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	last_used_at DATETIME, 
	revoked_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE
);
INSERT INTO "shortcut_tokens" VALUES(1,1,'iPhone','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','2026-11-10 10:00:00','2026-11-23 19:00:00',NULL);
INSERT INTO "shortcut_tokens" VALUES(2,1,'old iPad','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','2026-11-05 10:00:00',NULL,'2026-11-09 10:00:00');
CREATE TABLE user_sessions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "user_sessions" VALUES(1,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','2026-12-24 08:00:00','2026-11-24 08:00:00');
CREATE TABLE users (
	id INTEGER NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "users" VALUES(1,'alex','scrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA==$ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGk=',1,'2026-11-01 08:00:00');
INSERT INTO "users" VALUES(2,'sam','scrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA==$ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGk=',0,'2026-11-02 09:30:00');
CREATE INDEX ix_users_id ON users (id);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE INDEX ix_habits_id ON habits (id);
CREATE INDEX ix_habits_user_id ON habits (user_id);
CREATE INDEX ix_user_sessions_expires_at ON user_sessions (expires_at);
CREATE INDEX ix_user_sessions_id ON user_sessions (id);
CREATE UNIQUE INDEX ix_user_sessions_token_hash ON user_sessions (token_hash);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);
CREATE INDEX ix_habit_schedules_habit_id ON habit_schedules (habit_id);
CREATE INDEX ix_shortcut_tokens_habit_id ON shortcut_tokens (habit_id);
CREATE UNIQUE INDEX ix_shortcut_tokens_token_hash ON shortcut_tokens (token_hash);
COMMIT;
