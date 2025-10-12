# Release Notes - Körjournal v1.3.0

**Release Date:** 2025-10-12
**Branch:** add-user-login-v2 → main
**Previous Version:** v1.2.0

---

## 🎉 Overview

Version 1.3.0 is a major release that transforms Körjournal from a single-user application to a fully multi-tenant system with authentication, admin management, and per-user configuration. This release focuses on security, user management, and flexibility.

---

## ✨ New Features

### 🔐 Authentication & Security

- **Cookie-based Session Authentication**
  - Secure JWT-based sessions with httpOnly cookies
  - Configurable cookie settings (secure, samesite)
  - Automatic session validation on all protected endpoints

- **Password Security**
  - Bcrypt password hashing with salt
  - Minimum 8-character password requirement
  - Secure password change functionality

- **Rate Limiting**
  - Login endpoint limited to 5 attempts per minute
  - Protection against brute force attacks

- **User Authentication Flow**
  - Login page with username/password
  - Logout functionality
  - Middleware for frontend route protection
  - Automatic redirect to login for unauthenticated users

### 👥 Admin User Management

- **Admin Role System**
  - New `is_admin` field in User model
  - Admin privileges required for user management
  - Admin user automatically created on startup via env vars

- **Admin Interface** (`/admin`)
  - Create new users with username and password
  - View all users in the system
  - Delete users (with protections against deleting admins or self)
  - Clean, user-friendly interface with error handling

- **Admin API Endpoints**
  - `POST /admin/users` - Create user (admin only)
  - `GET /admin/users` - List all users (admin only)
  - `DELETE /admin/users/{id}` - Delete user (admin only)

### ⚙️ Per-User Home Assistant Configuration

- **Individual HA Instances**
  - Each user can configure their own Home Assistant instance
  - No longer dependent on global environment variables
  - Settings stored securely in database per user

- **Configurable Settings** (via `/settings` page)
  - **HA_BASE_URL** - Home Assistant URL
  - **HA_TOKEN** - Long-lived access token (encrypted)
  - **HA_ODOMETER_ENTITY** - Odometer sensor entity ID
  - **HA_FORCE_DOMAIN** - Force update service domain
  - **HA_FORCE_SERVICE** - Force update service name
  - **HA_FORCE_DATA** - Force update JSON payload

- **Improved Settings UI**
  - Clear sections for basic and advanced settings
  - Helpful descriptions and examples for each field
  - JSON validation for Force Data field
  - Test buttons for Poll and Force Update
  - Token masking (never displayed after save)

### 🏗️ Infrastructure Improvements

- **Database Migrations**
  - Alembic integration for schema versioning
  - Migration for `is_admin` field
  - Support for future schema changes

- **Multi-Tenant Data Isolation**
  - All trips are user-specific
  - All templates are user-specific
  - All settings are user-specific
  - No data leakage between users

- **Better Logging**
  - Structured logging throughout the application
  - Login attempt tracking
  - Admin action logging
  - Error tracking and debugging

---

## 🔄 API Changes

### New Endpoints

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/auth/login` | User login | No |
| POST | `/auth/logout` | User logout | No |
| GET | `/auth/me` | Get current user | Yes |
| POST | `/auth/change-password` | Change password | Yes |
| POST | `/admin/users` | Create user | Admin |
| GET | `/admin/users` | List users | Admin |
| DELETE | `/admin/users/{id}` | Delete user | Admin |
| GET | `/settings` | Get user settings | Yes |
| PUT | `/settings` | Update user settings | Yes |

### Protected Endpoints

All existing endpoints now require authentication:
- `/trips/*` - Trip management
- `/templates/*` - Template management
- `/integrations/home-assistant/*` - HA integration
- `/exports/*` - Data exports

### Response Changes

- **401 Unauthorized** - Returned when not authenticated
- **403 Forbidden** - Returned when lacking admin privileges
- **Settings endpoint** now returns per-user HA configuration

---

## 🚨 Breaking Changes

### Environment Variables

**Removed:**
- `HA_FORCE_DATA` - Too user-specific for global config

**Now Optional:**
- `HA_BASE_URL` - Users configure individually
- `HA_TOKEN` - Users configure individually
- `HA_ODOMETER_ENTITY` - Users configure individually

**Required:**
- `ADMIN_USERNAME` - Initial admin user
- `ADMIN_PASSWORD` - Initial admin password (min 8 chars)
- `SECRET_KEY` - JWT signing key

### Authentication Required

- All API endpoints (except `/auth/login`, `/auth/logout`, `/health`) now require authentication
- Frontend routes automatically redirect to `/login` if not authenticated
- Cookies must be enabled in the browser

### Data Migration

- Existing data will need to be associated with users
- No automatic migration provided - manual intervention required
- Recommend fresh install or manual data migration

---

## 📦 Installation & Setup

### Environment Variables

Update your `.env` file with the following required variables:

```bash
# Admin User (required)
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your-secure-password-here  # min 8 characters

# Security (required)
SECRET_KEY=your-secret-key-here  # Generate with: openssl rand -hex 32

# Optional: Global HA fallbacks (users override in settings)
HA_BASE_URL=
HA_TOKEN=
HA_ODOMETER_ENTITY=
HA_FORCE_DOMAIN=kia_uvo
HA_FORCE_SERVICE=force_update
```

### Database Migration

Run the Alembic migration to add the `is_admin` field:

```bash
cd api
alembic upgrade head
```

### First Startup

1. Start the application with docker-compose
2. Admin user will be created automatically on first startup
3. Login at `/login` with your admin credentials
4. Navigate to `/admin` to create additional users
5. Each user should configure their HA settings at `/settings`

---

## 🐛 Bug Fixes

- Fixed CORS configuration for authenticated requests
- Fixed cookie handling in frontend fetch calls
- Improved error messages throughout the application
- Fixed race conditions in trip overlap detection

---

## 📝 Technical Details

### Backend Changes

**New Files:**
- `api/app/security.py` - JWT and password hashing utilities
- `api/app/routes/auth.py` - Authentication routes (legacy, consolidated)
- `api/alembic/` - Database migration infrastructure
- `api/alembic/versions/001_add_is_admin_to_users.py` - Admin field migration

**Modified Files:**
- `api/app/main.py` - Protected routes, admin endpoints, auth flow
- `api/app/models.py` - Added `is_admin` field to User model
- `api/app/db.py` - Database connection improvements
- `api/requirements.txt` - Added bcrypt, python-jose, slowapi

### Frontend Changes

**New Files:**
- `web/app/login/page.tsx` - Login page
- `web/app/admin/page.tsx` - Admin user management
- `web/middleware.ts` - Authentication middleware

**Modified Files:**
- `web/app/layout.tsx` - Added Admin link to navigation
- `web/app/page.tsx` - Added authentication to fetch calls
- `web/app/settings/page.tsx` - Complete redesign with all HA fields
- `web/app/templates/page.tsx` - Added authentication

### Database Schema Changes

```sql
-- Add is_admin field to users table
ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT FALSE;
```

---

## 📊 Statistics

- **20 commits** since v1.2.0
- **25 files changed**
  - 3,151 insertions
  - 753 deletions
- **8 new files** created
- **17 existing files** modified

---

## 🔮 Future Enhancements

Potential features for future releases:
- Two-factor authentication (2FA)
- Password reset via email
- User profiles with additional metadata
- Audit log for admin actions
- Bulk user import/export
- Role-based permissions beyond admin/user
- OAuth/SSO integration

---

## 🙏 Credits

Developed with assistance from Claude Code (Anthropic).

---

## 📄 License

Same license as previous versions.

---

## 🆘 Support

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/JohanOstlund/korjournal-webapp/issues
- Pull Requests welcome!

---

## 🔗 Links

- **Repository:** https://github.com/JohanOstlund/korjournal-webapp
- **Pull Request:** https://github.com/JohanOstlund/korjournal-webapp/pull/[PR_NUMBER]
- **Previous Release:** v1.2.0

---

**Happy journaling! 🚗📝**
