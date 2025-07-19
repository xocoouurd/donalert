# Flask E-Commerce Project Structure Documentation

This document outlines the architectural patterns and organizational structure used in this Flask-based e-commerce application. Use this as a blueprint for creating similar projects with the same modular, scalable structure.

## Project Root Structure

```
project_root/
├── run.py                    # Application entry point
├── config.py                 # Configuration management
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in git)
├── CLAUDE.md                 # Claude Code project instructions
├── app/                      # Main application package
├── migrations/               # Database migration files
├── venv/                     # Virtual environment
└── docs/                     # Project documentation
```

## Core Architecture Components

### 1. Application Entry Point (`run.py`)

- Imports the `create_app()` factory function
- Initializes SocketIO for real-time features
- Runs the application with specific host/port configuration
- Keeps application instantiation separate from configuration

### 2. Configuration Management (`config.py`)

- Single `Config` class containing all application settings
- Uses `python-dotenv` to load environment variables from `.env`
- Centralizes database connection strings, upload settings, and security keys
- Environment-specific configurations (development, production)

### 3. Environment Variables (`.env`)

Essential variables to define:

- `SECRET_KEY` - Flask security key
- `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` - Database credentials
- `UPLOAD_FOLDER` - File upload directory path
- `MAX_IMAGE_SIZE_MB` - Image upload size limit
- `SERVER_NAME`, `PREFERRED_URL_SCHEME` - Server configuration

## Application Package Structure (`app/`)

### Flask Application Factory Pattern

#### `app/__init__.py`

- Contains `create_app()` function implementing the application factory pattern
- Initializes all Flask extensions (SQLAlchemy, Flask-Login, Flask-Migrate)
- Registers all blueprint modules for modular routing
- Sets up context processors and user authentication
- Imports all models to ensure Flask-Migrate can detect them

#### `app/extensions.py`

- Centralizes Flask extension instances
- Creates singleton instances: `db`, `login_manager`, `migrate`, `socketio`
- Extensions are initialized in `create_app()` but defined here for import consistency

### Modular Architecture

**Model Design Patterns:**

- Each model file contains related database tables
- Uses SQLAlchemy ORM with proper relationships
- Includes model methods for business logic
- Foreign key relationships properly defined with cascading deletes

**Route Design Patterns:**

- Each route file implements a Flask Blueprint
- Blueprints registered in `create_app()` function
- Route functions include proper error handling
- Authentication decorators (`@login_required`) applied where needed
- JSON API endpoints and HTML template rendering separated clearly

**Utility Design Patterns:**

- Reusable functions that don't belong to specific models
- Business logic separated from route handlers
- Integration code for external services
- Helper functions for common operations

#### File Upload Management

- **Organized by content type**: Separate subdirectories for different upload types
- **UUID-based filenames**: Prevents naming conflicts and ensures uniqueness
- **Automatic image processing**: PIL integration for resizing and optimization
- **Size validation**: Configurable maximum file sizes in `config.py`
- **Format validation**: Support for PNG, JPG, JPEG, GIF, WebP formats

### Template Structure (`app/templates/`)

## Database Management

### Migration System

- **Flask-Migrate**: Handles database schema changes
- **Migration files**: Stored in `migrations/versions/`
- **Migration commands**: `flask db migrate`, `flask db upgrade`, `flask db downgrade`
- **Version control**: All migrations tracked in git for deployment consistency

### Database Schema Patterns

- **Proper relationships**: Foreign keys with cascade options
- **Indexing strategy**: Indexed fields for performance
- **Data validation**: Model-level constraints and validations
- **Soft deletes**: Where applicable, use status flags instead of hard deletes

## Development Workflow

### Virtual Environment

- **Isolation**: Project dependencies isolated in `venv/` directory
- **Activation**: `source venv/bin/activate` (Linux/Mac) or `venv\Scripts\activate` (Windows)
- **Dependencies**: Managed through `requirements.txt`

### Environment Configuration

- **Local development**: `.env` file for environment variables
- **Production deployment**: Environment variables set at server level
- **Configuration classes**: Extensible for different environments

### Code Organization Principles

- **Separation of concerns**: Models, routes, and utilities in separate modules
- **Blueprint modularity**: Each feature area has its own blueprint
- **Factory pattern**: Application creation through factory function
- **Extension initialization**: Centralized extension management

## Security Considerations

### Authentication & Authorization

- **Flask-Login**: Session management and user authentication
- **Password hashing**: Werkzeug's secure password hashing
- **Role-based access**: User roles for admin functionality
- **Route protection**: Login required decorators on protected routes

### File Upload Security

- **Filename sanitization**: Secure filename generation
- **File type validation**: Whitelist of allowed file extensions
- **Size limitations**: Configurable upload size limits
- **Storage isolation**: Uploads stored outside application code

### Configuration Security

- **Environment variables**: Sensitive data not hardcoded
- **Secret key management**: Proper secret key handling
- **Database credentials**: Secure credential management

## Scalability Patterns

### Modular Design

- **Blueprint architecture**: Easy to add new feature modules
- **Model organization**: Related functionality grouped together
- **Utility functions**: Reusable code components
- **Template inheritance**: Consistent UI patterns

### Database Optimization

- **Relationship loading**: Proper use of lazy/eager loading
- **Query optimization**: Efficient database queries
- **Migration management**: Structured schema evolution
- **Connection pooling**: Database connection management

### Asset Management

- **Static file organization**: Logical asset grouping
- **Image optimization**: Automatic image processing
- **Upload management**: Structured file storage
- **Cache considerations**: Static asset caching strategies

## Deployment Considerations

### Production Setup

- **WSGI compatibility**: Standard Flask WSGI application
- **Environment configuration**: Production environment variables
- **Database setup**: MySQL/MariaDB configuration
- **Static file serving**: Web server static file handling

### Monitoring & Maintenance

- **Error logging**: Proper error handling and logging
- **Database maintenance**: Regular migration applications
- **File cleanup**: Upload directory management
- **Security updates**: Regular dependency updates

This structure provides a solid foundation for Flask e-commerce applications with clear separation of concerns, modular architecture, and scalable patterns that can be replicated across different projects.
