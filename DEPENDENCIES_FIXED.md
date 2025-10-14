

## 🚀 Quick Installation

Run the automated installation script:

```bash
./install.sh
```

This will:
- Create a virtual environment
- Install all dependencies 
- Set up environment files
- Install frontend dependencies (if Node.js available)

## 🔍 Validate Installation

Check if everything is working:

```bash
python3 validate_deps.py
```


## 🏃‍♂️ Manual Installation

If you prefer manual installation:

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install ErrorLogger
cd projects/ErrorLogger
pip install -e .
cd ../..

# Install AI Service dependencies
cd projects/ai_service/backend  
pip install -r requirements.txt
cd ../../..

# Install frontend (requires Node.js)
cd projects/ai_service/frontend
npm install
cd ../../..
```

## ⚙️ Configuration

Copy the example environment files and customize as needed:

```bash
cp projects/ai_service/backend/.env.example projects/ai_service/backend/.env
cp projects/ErrorLogger/.env.example projects/ErrorLogger/.env
```

## 🏃‍♂️ Running the Services

1. **Start ErrorLogger** (in one terminal):
```bash
source venv/bin/activate
cd projects/ErrorLogger
python error_server.py
```

2. **Start AI Service Backend** (in another terminal):
```bash
source venv/bin/activate  
cd projects/ai_service/backend
python app.py
```

3. **Start Frontend** (in a third terminal):
```bash
cd projects/ai_service/frontend
npm start
```