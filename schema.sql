/* =========================================================
   MINI_GITHUB - Schéma MySQL solide + triggers utiles
   (MySQL 8+ recommandé)
   ========================================================= */

CREATE DATABASE IF NOT EXISTS code_share
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE code_share;

-- Supprimer d'abord les tables dépendantes
DROP TABLE IF EXISTS project_activity;
DROP TABLE IF EXISTS project_tags;
DROP TABLE IF EXISTS tags;
DROP TABLE IF EXISTS followers;
DROP TABLE IF EXISTS stars;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS files;
DROP TABLE IF EXISTS project_members;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS users;

/* =========================================================
   TABLE: users
   ========================================================= */
CREATE TABLE users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(30) NOT NULL,
  email VARCHAR(100) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  bio VARCHAR(500) NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  -- Normalisation (évite Alice vs alice)
  username_norm VARCHAR(30)
    GENERATED ALWAYS AS (LOWER(TRIM(username))) STORED,
  email_norm VARCHAR(100)
    GENERATED ALWAYS AS (LOWER(TRIM(email))) STORED,

  CONSTRAINT uq_users_username_norm UNIQUE (username_norm),
  CONSTRAINT uq_users_email_norm UNIQUE (email_norm),

  CONSTRAINT chk_username_len CHECK (CHAR_LENGTH(username) BETWEEN 3 AND 30),
  CONSTRAINT chk_username_format CHECK (username REGEXP '^[a-zA-Z0-9_]+$'),
  CONSTRAINT chk_email_format CHECK (email REGEXP '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$')
) ENGINE=InnoDB;

CREATE INDEX idx_users_created_at ON users(created_at);

/* =========================================================
   TABLE: projects
   ========================================================= */
CREATE TABLE projects (
  id INT AUTO_INCREMENT PRIMARY KEY,
  owner_id INT NOT NULL,
  title VARCHAR(100) NOT NULL,
  description VARCHAR(2000) NULL,
  language VARCHAR(50) NULL,
  is_private BOOLEAN NOT NULL DEFAULT FALSE,
  status ENUM('active','archived') NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP,

  CONSTRAINT fk_projects_owner
    FOREIGN KEY (owner_id) REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT chk_project_title_len CHECK (CHAR_LENGTH(title) BETWEEN 3 AND 100)
) ENGINE=InnoDB;

CREATE INDEX idx_projects_owner ON projects(owner_id);
CREATE INDEX idx_projects_visibility ON projects(is_private);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_created_at ON projects(created_at);

/* =========================================================
   TABLE: project_members
   ========================================================= */
CREATE TABLE project_members (
  project_id INT NOT NULL,
  user_id INT NOT NULL,
  role ENUM('owner','admin','member') NOT NULL DEFAULT 'member',
  joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (project_id, user_id),

  CONSTRAINT fk_pm_project
    FOREIGN KEY (project_id) REFERENCES projects(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_pm_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_pm_user ON project_members(user_id);
CREATE INDEX idx_pm_role ON project_members(project_id, role);

/* =========================================================
   TABLE: files
   ========================================================= */
CREATE TABLE files (
  id INT AUTO_INCREMENT PRIMARY KEY,
  project_id INT NOT NULL,
  uploaded_by INT NOT NULL,
  filename VARCHAR(255) NOT NULL,
  filepath VARCHAR(500) NOT NULL,
  filesize BIGINT NOT NULL,
  sha256 CHAR(64) NULL,
  uploaded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_files_project
    FOREIGN KEY (project_id) REFERENCES projects(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_files_uploader
    FOREIGN KEY (uploaded_by) REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT uq_files_project_filepath UNIQUE (project_id, filepath),

  CONSTRAINT chk_filesize_positive CHECK (filesize > 0),
  CONSTRAINT chk_filesize_limit CHECK (filesize <= 10485760)
) ENGINE=InnoDB;

CREATE INDEX idx_files_project ON files(project_id);
CREATE INDEX idx_files_uploader ON files(uploaded_by);
CREATE INDEX idx_files_uploaded_at ON files(uploaded_at);
CREATE INDEX idx_files_sha256 ON files(sha256);

/* =========================================================
   TABLE: comments
   ========================================================= */
CREATE TABLE comments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  project_id INT NOT NULL,
  user_id INT NOT NULL,
  message VARCHAR(1000) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_comments_project
    FOREIGN KEY (project_id) REFERENCES projects(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_comments_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT chk_comment_len CHECK (CHAR_LENGTH(message) BETWEEN 1 AND 1000)
) ENGINE=InnoDB;

CREATE INDEX idx_comments_project_created ON comments(project_id, created_at);
CREATE INDEX idx_comments_user ON comments(user_id);

/* =========================================================
   TABLE: stars
   ========================================================= */
CREATE TABLE stars (
  user_id INT NOT NULL,
  project_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (user_id, project_id),

  CONSTRAINT fk_stars_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_stars_project
    FOREIGN KEY (project_id) REFERENCES projects(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_stars_project ON stars(project_id);
CREATE INDEX idx_stars_user_created ON stars(user_id, created_at);

/* =========================================================
   TABLE: followers
   ========================================================= */
CREATE TABLE followers (
  follower_id INT NOT NULL,
  following_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (follower_id, following_id),

  CONSTRAINT fk_followers_follower
    FOREIGN KEY (follower_id) REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_followers_following
    FOREIGN KEY (following_id) REFERENCES users(id)
    ON DELETE CASCADE,

  CONSTRAINT chk_no_self_follow CHECK (follower_id <> following_id)
) ENGINE=InnoDB;

CREATE INDEX idx_followers_following ON followers(following_id);
CREATE INDEX idx_followers_follower ON followers(follower_id);

/* =========================================================
   TABLE: tags + project_tags (tags normalisés)
   ========================================================= */
CREATE TABLE tags (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(50) NOT NULL,

  name_norm VARCHAR(50)
    GENERATED ALWAYS AS (LOWER(TRIM(name))) STORED,

  CONSTRAINT uq_tags_name_norm UNIQUE (name_norm),
  CONSTRAINT chk_tag_len CHECK (CHAR_LENGTH(name) BETWEEN 1 AND 50),
  CONSTRAINT chk_tag_format CHECK (name REGEXP '^[a-zA-Z0-9_\\-]+$')
) ENGINE=InnoDB;

CREATE TABLE project_tags (
  project_id INT NOT NULL,
  tag_id INT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  PRIMARY KEY (project_id, tag_id),

  CONSTRAINT fk_pt_project
    FOREIGN KEY (project_id) REFERENCES projects(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_pt_tag
    FOREIGN KEY (tag_id) REFERENCES tags(id)
    ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_project_tags_tag ON project_tags(tag_id);

/* =========================================================
   TABLE: project_activity (journal d’activité)
   ========================================================= */
CREATE TABLE project_activity (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  project_id INT NOT NULL,
  user_id INT NULL,
  action ENUM(
    'created_project',
    'joined_project',
    'left_project',
    'uploaded_file',
    'commented',
    'starred'
  ) NOT NULL,
  entity_type ENUM('project','member','file','comment','star') NOT NULL,
  entity_id BIGINT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT fk_activity_project
    FOREIGN KEY (project_id) REFERENCES projects(id)
    ON DELETE CASCADE,

  CONSTRAINT fk_activity_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE INDEX idx_activity_project_created ON project_activity(project_id, created_at);
CREATE INDEX idx_activity_user_created ON project_activity(user_id, created_at);