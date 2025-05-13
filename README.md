# SourceHub

SourceHub is a GitHub-like platform that allows users to share and manage their source code projects without requiring Git knowledge. It provides features like project management, issue tracking, releases, and programming language statistics.

## Features

- User authentication and profiles
- Project creation and management
- Source code upload and management
- Issue tracking system
- Release management
- Programming language statistics
- Modern and responsive UI

## Requirements

- Python 3.8 or higher
- Flask and other dependencies listed in requirements.txt

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/sourcehub.git
cd sourcehub
```

2. Create a virtual environment and activate it:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
flask db init
flask db migrate
flask db upgrade
```

5. Run the application:
```bash
python main.py
```

The application will be available at `http://localhost:5000`

## Project Structure

```
sourcehub/
├── main.py              # Main application file
├── requirements.txt     # Project dependencies
├── templates/          # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── project.html
│   ├── new_project.html
│   └── profile.html
└── uploads/           # Directory for uploaded source code
```

## Contributing

1. Fork the repository
2. Create a new branch for your feature
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 