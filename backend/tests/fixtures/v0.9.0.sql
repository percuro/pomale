BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('0007');
CREATE TABLE audit_events (
	id INTEGER NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	event VARCHAR(48) NOT NULL, 
	actor_user_id INTEGER, 
	actor_username VARCHAR(80), 
	target_user_id INTEGER, 
	target_username VARCHAR(80), 
	ip_prefix VARCHAR(64), 
	details TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(target_user_id) REFERENCES users (id) ON DELETE SET NULL
);
INSERT INTO "audit_events" VALUES(1,'2026-11-24 08:00:00','auth.login',1,'alex',NULL,NULL,NULL,'{"method": "password"}');
CREATE TABLE "checkins" (
	habit_id INTEGER NOT NULL, 
	local_date DATE NOT NULL, 
	done BOOLEAN NOT NULL, 
	version INTEGER NOT NULL, 
	last_op_id VARCHAR(64), 
	updated_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	value INTEGER, 
	note VARCHAR(500), 
	PRIMARY KEY (habit_id, local_date), 
	CONSTRAINT ck_checkins_value CHECK (value IS NULL OR value BETWEEN 0 AND 9999), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE
);
INSERT INTO "checkins" VALUES(1,'2026-11-23',1,1,'op-1','2026-11-23 19:00:00',NULL,'Kapitel 3');
INSERT INTO "checkins" VALUES(1,'2026-11-24',0,2,'op-2','2026-11-24 19:00:00',NULL,NULL);
INSERT INTO "checkins" VALUES(2,'2026-11-19',1,1,NULL,'2026-11-19 18:00:00',NULL,NULL);
INSERT INTO "checkins" VALUES(3,'2026-11-23',1,1,NULL,'2026-11-23 18:00:00',NULL,NULL);
INSERT INTO "checkins" VALUES(4,'2026-11-25',1,3,'op-3','2026-11-25 12:00:00',5,NULL);
CREATE TABLE habit_groups (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(60) NOT NULL, 
	sort_order INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT uq_habit_groups_user_name UNIQUE (user_id, name)
);
INSERT INTO "habit_groups" VALUES(1,1,'Morgens',1);
CREATE TABLE habit_pauses (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	habit_id INTEGER, 
	start_on DATE NOT NULL, 
	end_on DATE NOT NULL, 
	reason VARCHAR(80), 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_habit_pauses_range CHECK (end_on >= start_on), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "habit_pauses" VALUES(1,1,NULL,'2026-11-10','2026-11-12','krank','2026-11-12 08:00:00');
INSERT INTO "habit_pauses" VALUES(2,2,3,'2026-12-20','2026-12-31',NULL,'2026-11-24 09:00:00');
CREATE TABLE habit_reminders (
	id INTEGER NOT NULL, 
	habit_id INTEGER NOT NULL, 
	time TIME NOT NULL, 
	last_sent_on DATE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE, 
	CONSTRAINT uq_habit_reminders_time UNIQUE (habit_id, time)
);
INSERT INTO "habit_reminders" VALUES(1,1,'07:30:00.000000','2026-11-25');
INSERT INTO "habit_reminders" VALUES(2,1,'20:00:00.000000',NULL);
INSERT INTO "habit_reminders" VALUES(3,4,'00:30:00.000000',NULL);
CREATE TABLE "habit_schedules" (
	id INTEGER NOT NULL, 
	habit_id INTEGER NOT NULL, 
	valid_from DATE NOT NULL, 
	weekdays INTEGER NOT NULL, 
	goal_type VARCHAR(16) DEFAULT 'days' NOT NULL, 
	target INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_habit_schedule_valid_from UNIQUE (habit_id, valid_from), 
	CONSTRAINT ck_habit_schedule_weekdays CHECK (weekdays BETWEEN 0 AND 127), 
	CONSTRAINT ck_habit_schedule_goal CHECK ((goal_type = 'days' AND target IS NULL) OR (goal_type = 'weekly_count' AND target IS NOT NULL AND target BETWEEN 1 AND 7) OR (goal_type = 'quantity' AND target IS NOT NULL AND target BETWEEN 1 AND 9999)), 
	FOREIGN KEY(habit_id) REFERENCES habits (id) ON DELETE CASCADE
);
INSERT INTO "habit_schedules" VALUES(1,1,'2026-11-01',127,'days',NULL);
INSERT INTO "habit_schedules" VALUES(2,1,'2026-11-16',31,'days',NULL);
INSERT INTO "habit_schedules" VALUES(3,2,'2026-11-01',127,'days',NULL);
INSERT INTO "habit_schedules" VALUES(4,2,'2026-11-21',0,'days',NULL);
INSERT INTO "habit_schedules" VALUES(5,3,'2026-11-02',21,'days',NULL);
INSERT INTO "habit_schedules" VALUES(6,3,'2026-11-23',127,'weekly_count',3);
INSERT INTO "habit_schedules" VALUES(7,4,'2026-11-25',127,'quantity',8);
CREATE TABLE "habits" (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	cue VARCHAR(200), 
	sort_order INTEGER NOT NULL, 
	archived_on DATE, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	unit VARCHAR(20), 
	color VARCHAR(16), 
	group_id INTEGER, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_habits_group_id_habit_groups FOREIGN KEY(group_id) REFERENCES habit_groups (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "habits" VALUES(1,1,'Lesen','nach dem Frühstück',1,NULL,'2026-11-01 08:05:00',NULL,'teal',1);
INSERT INTO "habits" VALUES(2,1,'Dehnen',NULL,2,'2026-11-20','2026-11-01 08:06:00',NULL,NULL,NULL);
INSERT INTO "habits" VALUES(3,2,'Running',NULL,1,NULL,'2026-11-02 09:40:00',NULL,'blue',NULL);
INSERT INTO "habits" VALUES(4,1,'Wasser',NULL,3,NULL,'2026-11-25 08:00:00','Gläser',NULL,1);
CREATE TABLE instance_secrets (
	name VARCHAR(64) NOT NULL, 
	value TEXT NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (name)
);
INSERT INTO "instance_secrets" VALUES('vapid_private_key','not-a-real-key','2026-11-25 14:00:00');
CREATE TABLE invitations (
	id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	purpose VARCHAR(16) NOT NULL, 
	role VARCHAR(16), 
	target_user_id INTEGER, 
	note VARCHAR(80), 
	created_by_user_id INTEGER, 
	expires_at DATETIME NOT NULL, 
	used_at DATETIME, 
	used_by_user_id INTEGER, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id) ON DELETE SET NULL, 
	FOREIGN KEY(target_user_id) REFERENCES users (id) ON DELETE CASCADE, 
	FOREIGN KEY(used_by_user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE TABLE oidc_identities (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	issuer VARCHAR(255) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	email VARCHAR(255), 
	preferred_username VARCHAR(80), 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	last_login_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	CONSTRAINT uq_oidc_identities_issuer_subject UNIQUE (issuer, subject)
);
INSERT INTO "oidc_identities" VALUES(1,2,'https://auth.example.org','sub-sam','sam@example.org','sam','2026-11-02 09:30:00','2026-11-24 09:00:00');
CREATE TABLE oidc_login_states (
	id INTEGER NOT NULL, 
	state_hash VARCHAR(64) NOT NULL, 
	purpose VARCHAR(16) NOT NULL, 
	code_verifier VARCHAR(128) NOT NULL, 
	nonce VARCHAR(128) NOT NULL, 
	user_id INTEGER, 
	session_id INTEGER, 
	invitation_id INTEGER, 
	payload TEXT, 
	return_to VARCHAR(64), 
	expires_at DATETIME NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(invitation_id) REFERENCES invitations (id) ON DELETE CASCADE, 
	FOREIGN KEY(session_id) REFERENCES user_sessions (id) ON DELETE CASCADE, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE TABLE push_subscriptions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	session_id INTEGER, 
	endpoint VARCHAR(1000) NOT NULL, 
	p256dh VARCHAR(100) NOT NULL, 
	auth VARCHAR(40) NOT NULL, 
	user_agent VARCHAR(200), 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	last_success_at DATETIME, 
	last_error VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES user_sessions (id) ON DELETE SET NULL, 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
	UNIQUE (endpoint)
);
INSERT INTO "push_subscriptions" VALUES(1,1,1,'https://fcm.googleapis.com/fcm/send/alex','key','auth','Mozilla/5.0 (iPhone)','2026-11-25 14:00:00','2026-11-25 19:30:02',NULL);
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
INSERT INTO "shortcut_tokens" VALUES(1,1,'iPhone','bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb','2026-11-10 10:00:00','2026-11-24 19:00:00',NULL);
INSERT INTO "shortcut_tokens" VALUES(2,3,'Watch','cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc','2026-11-11 10:00:00',NULL,NULL);
INSERT INTO "shortcut_tokens" VALUES(5,1,'old phone','eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee','2026-11-05 10:00:00','2026-11-06 07:00:00','2026-11-09 12:00:00');
CREATE TABLE user_sessions (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, last_seen_at DATETIME, user_agent VARCHAR(255), auth_method VARCHAR(16) DEFAULT 'password' NOT NULL, authenticated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
INSERT INTO "user_sessions" VALUES(1,1,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa','2026-12-24 08:00:00','2026-11-24 08:00:00','2026-11-24 20:00:00','Mozilla/5.0 (iPhone)','password','2026-11-24 08:00:00');
INSERT INTO "user_sessions" VALUES(2,2,'dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd','2026-12-24 09:00:00','2026-11-24 09:00:00',NULL,NULL,'oidc','2026-11-24 09:00:00');
CREATE TABLE "users" (
	id INTEGER NOT NULL, 
	username VARCHAR(80) NOT NULL, 
	password_hash VARCHAR(255), 
	is_active BOOLEAN NOT NULL, 
	created_at DATETIME DEFAULT (CURRENT_TIMESTAMP) NOT NULL, 
	role VARCHAR(16) DEFAULT 'user' NOT NULL, 
	display_name VARCHAR(80), 
	timezone VARCHAR(64), 
	locale VARCHAR(8), 
	last_seen_at DATETIME, day_end_hour INTEGER DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id)
);
INSERT INTO "users" VALUES(1,'alex','scrypt$16384$8$1$c2FsdHNhbHRzYWx0c2FsdA==$ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGlnZXN0ZGk=',1,'2026-11-01 08:00:00','admin','Alex','Pacific/Kiritimati','de','2026-11-24 20:00:00',2);
INSERT INTO "users" VALUES(2,'sam',NULL,1,'2026-11-02 09:30:00','user',NULL,NULL,'en',NULL,0);
CREATE INDEX ix_user_sessions_expires_at ON user_sessions (expires_at);
CREATE INDEX ix_user_sessions_id ON user_sessions (id);
CREATE UNIQUE INDEX ix_user_sessions_token_hash ON user_sessions (token_hash);
CREATE INDEX ix_user_sessions_user_id ON user_sessions (user_id);
CREATE INDEX ix_shortcut_tokens_habit_id ON shortcut_tokens (habit_id);
CREATE UNIQUE INDEX ix_shortcut_tokens_token_hash ON shortcut_tokens (token_hash);
CREATE INDEX ix_invitations_created_by_user_id ON invitations (created_by_user_id);
CREATE INDEX ix_invitations_target_user_id ON invitations (target_user_id);
CREATE UNIQUE INDEX ix_invitations_token_hash ON invitations (token_hash);
CREATE INDEX ix_audit_events_actor_user_id ON audit_events (actor_user_id);
CREATE INDEX ix_audit_events_created_at ON audit_events (created_at);
CREATE INDEX ix_audit_events_event ON audit_events (event);
CREATE INDEX ix_audit_events_target_user_id ON audit_events (target_user_id);
CREATE UNIQUE INDEX ix_oidc_identities_user_id ON oidc_identities (user_id);
CREATE INDEX ix_oidc_login_states_expires_at ON oidc_login_states (expires_at);
CREATE UNIQUE INDEX ix_oidc_login_states_state_hash ON oidc_login_states (state_hash);
CREATE INDEX ix_users_id ON users (id);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE INDEX ix_habit_groups_user_id ON habit_groups (user_id);
CREATE INDEX ix_habit_pauses_habit_id ON habit_pauses (habit_id);
CREATE INDEX ix_habit_pauses_user_id ON habit_pauses (user_id);
CREATE INDEX ix_habit_schedules_habit_id ON habit_schedules (habit_id);
CREATE INDEX ix_habits_id ON habits (id);
CREATE INDEX ix_habits_user_id ON habits (user_id);
CREATE INDEX ix_habits_group_id ON habits (group_id);
CREATE INDEX ix_push_subscriptions_session_id ON push_subscriptions (session_id);
CREATE INDEX ix_push_subscriptions_user_id ON push_subscriptions (user_id);
CREATE INDEX ix_habit_reminders_habit_id ON habit_reminders (habit_id);
COMMIT;
