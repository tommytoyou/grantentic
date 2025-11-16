# Deployment Guide - Streamlit on Replit

This guide covers deploying the Grantentic Streamlit web application on Replit and troubleshooting common issues.

## Quick Deploy on Replit

### Automatic Deployment (Recommended)

1. **Fork or Import** this Repl
2. **Click "Run"** button
3. **Wait** for Streamlit to start (15-30 seconds)
4. **Access** via the webview panel

The app will automatically:
- Install dependencies
- Start Streamlit on port 5000
- Configure for Replit deployment
- Pass health checks

## Configuration Files

### `.streamlit/config.toml`

This file configures Streamlit for Replit deployment:

```toml
[server]
headless = true                    # Run without browser
port = 5000                        # Replit requires port 5000
address = "0.0.0.0"               # Accept all connections
enableCORS = false                # Disable CORS for Replit
enableXsrfProtection = false      # Disable XSRF for Replit
enableWebsocketCompression = true # Better performance
fileWatcherType = "none"          # Disable file watching
runOnSave = false                 # Faster startup
```

**Why these settings:**
- `enableXsrfProtection = false` - Required for Replit's proxy system
- `address = "0.0.0.0"` - Allows external connections
- `fileWatcherType = "none"` - Reduces resource usage
- `headless = true` - Required for server deployment

### `.replit`

Configures Replit workflows and deployment:

```toml
[deployment]
deploymentTarget = "vm"
run = ["sh", "-c", "streamlit run app.py --server.port 5000 --server.address 0.0.0.0 --server.headless true --server.enableCORS false --server.enableXsrfProtection false"]

[deployment.healthcheck]
path = "/"                # Health check endpoint
timeout = 30              # 30 second timeout
interval = 5              # Check every 5 seconds
retries = 3               # Retry 3 times before failing
```

**Health Check Configuration:**
- Replit checks if app responds on `/` endpoint
- App must respond within 30 seconds
- Checked every 5 seconds
- 3 retries before marking as failed

## Common Deployment Issues

### Issue 1: Health Check Timeout

**Symptoms:**
```
Health check failed: no response on / endpoint
Deployment failed after timeout
```

**Causes:**
- App taking too long to start
- Modules loading slowly
- Database connections hanging

**Solutions:**

1. **Check startup time:**
```bash
time streamlit run app.py
```

2. **Optimize imports** (already implemented):
   - Lazy loading of heavy modules
   - Import only when needed
   - Fast initial page load

3. **Check logs:**
```bash
# View Streamlit logs
streamlit run app.py --logger.level debug
```

4. **Increase health check timeout:**
Edit `.replit`:
```toml
[deployment.healthcheck]
timeout = 60  # Increase to 60 seconds
```

### Issue 2: XSRF Protection Error

**Symptoms:**
```
403 Forbidden
XSRF token mismatch
Cookie not set
```

**Cause:**
- XSRF protection enabled (default)
- Replit's proxy interferes with XSRF tokens

**Solution:**
Already fixed in `.streamlit/config.toml`:
```toml
[server]
enableXsrfProtection = false
```

If still occurring, add to command line:
```bash
streamlit run app.py --server.enableXsrfProtection false
```

### Issue 3: Port Not Accessible

**Symptoms:**
```
Connection refused on port 5000
Cannot access application
```

**Solutions:**

1. **Verify port binding:**
```bash
lsof -i :5000
# Should show streamlit process
```

2. **Check address binding:**
Must bind to `0.0.0.0`, not `localhost`:
```bash
streamlit run app.py --server.address 0.0.0.0
```

3. **Check firewall:**
Replit should handle this automatically, but verify:
```bash
# Check if port is listening
netstat -tuln | grep 5000
```

### Issue 4: CORS Errors

**Symptoms:**
```
CORS policy blocked
Cross-origin request failed
```

**Solution:**
Already fixed in config:
```toml
[server]
enableCORS = false
```

For development, can enable with specific origins:
```toml
[server]
enableCORS = true
corsAllowOrigins = ["*"]
```

### Issue 5: WebSocket Connection Failed

**Symptoms:**
```
WebSocket connection failed
App not updating in real-time
```

**Solutions:**

1. **Enable WebSocket compression:**
Already enabled in config:
```toml
[server]
enableWebsocketCompression = true
```

2. **Check browser console:**
Look for WebSocket errors

3. **Try different browser:**
Some browsers have strict WebSocket policies

### Issue 6: Slow Startup

**Symptoms:**
- App takes >30 seconds to start
- Health checks timing out
- First load very slow

**Solutions:**

1. **Lazy module loading** (already implemented):
```python
# Modules only load when needed
lazy_load_modules()
```

2. **Disable file watcher:**
Already disabled in config:
```toml
[server]
fileWatcherType = "none"
runOnSave = false
```

3. **Reduce initial computations:**
- Don't load data on startup
- Load data only when tabs are accessed
- Cache expensive operations

4. **Use caching:**
```python
@st.cache_data
def load_agency_requirements(agency):
    # Cached for faster subsequent loads
    pass
```

## Testing Deployment

### Manual Health Check

Run the health check script:

```bash
python healthcheck.py
```

Expected output:
```
============================================================
Streamlit Health Check
============================================================
Checking health of http://localhost:5000...
Attempt 1/3...
✓ Health check passed! Status code: 200
✓ App is responding correctly

✓ All health checks passed!
```

### Test via cURL

```bash
# Basic connectivity test
curl -I http://localhost:5000

# Expected response:
# HTTP/1.1 200 OK
# Content-Type: text/html
```

### Test via Browser

1. Open `http://localhost:5000`
2. Page should load within 10 seconds
3. Sidebar should appear
4. No errors in browser console

## Deployment Checklist

Before deploying, verify:

- [ ] `.streamlit/config.toml` exists with correct settings
- [ ] `.replit` has proper deployment configuration
- [ ] `requirements.txt` includes `streamlit>=1.30.0`
- [ ] App starts successfully locally
- [ ] Health check passes (run `python healthcheck.py`)
- [ ] No XSRF errors
- [ ] Port 5000 is accessible
- [ ] WebSocket connections work
- [ ] All tabs load without errors

## Environment Variables

Required for Replit deployment:

```bash
# Set in Replit Secrets
AI_INTEGRATIONS_ANTHROPIC_API_KEY=sk-...
AI_INTEGRATIONS_ANTHROPIC_BASE_URL=https://...

# Optional
GRANT_AGENCY=nsf  # Default agency
OUTPUT_DIR=outputs  # Output directory
```

**Setting in Replit:**
1. Click "Tools" → "Secrets"
2. Add each variable
3. Restart deployment

## Performance Optimization

### 1. Lazy Loading

Already implemented:
```python
# Load modules only when needed
def lazy_load_modules():
    global CostTracker, GrantAgent, ...
    # Import only when function is called
```

### 2. Session State Caching

```python
# Cache expensive operations
if 'agency_loader' not in st.session_state:
    st.session_state.agency_loader = load_agency_requirements(agency)
```

### 3. Disable Unnecessary Features

Already disabled:
- File watching
- Run on save
- Usage stats collection

### 4. Use st.cache_data

For expensive operations:
```python
@st.cache_data(ttl=3600)  # Cache for 1 hour
def load_company_data():
    with open('data/company_context.json') as f:
        return json.load(f)
```

## Monitoring

### Check Application Status

```bash
# Check if running
ps aux | grep streamlit

# Check port
lsof -i :5000

# Check logs
tail -f ~/.streamlit/logs/streamlit.log
```

### Monitor Resource Usage

```bash
# CPU and memory
top -p $(pgrep -f streamlit)

# Detailed stats
htop
```

### View Streamlit Logs

```bash
# Real-time logs
streamlit run app.py --logger.level debug

# Log file location
~/.streamlit/logs/
```

## Troubleshooting Commands

```bash
# Kill existing Streamlit processes
pkill -f streamlit

# Clear Streamlit cache
rm -rf ~/.streamlit/cache

# Reset everything
rm -rf ~/.streamlit
streamlit run app.py

# Test with verbose logging
streamlit run app.py --logger.level debug --server.logLevel debug
```

## Production Deployment

For production deployments:

1. **Use proper secrets management**
   - Store API keys in Replit Secrets
   - Never commit credentials

2. **Enable security features** (if not using Replit proxy):
   ```toml
   [server]
   enableXsrfProtection = true
   enableCORS = true
   corsAllowOrigins = ["https://yourdomain.com"]
   ```

3. **Add authentication** (optional):
   ```python
   import streamlit_authenticator as stauth
   # Add login page
   ```

4. **Monitor performance:**
   - Use Replit's built-in monitoring
   - Set up error tracking
   - Monitor API costs

5. **Set resource limits:**
   ```toml
   [server]
   maxUploadSize = 200  # MB
   maxMessageSize = 200  # MB
   ```

## Getting Help

If deployment issues persist:

1. **Check Replit Status:**
   - https://status.replit.com

2. **Review Streamlit Docs:**
   - https://docs.streamlit.io/deploy

3. **Check Logs:**
   ```bash
   streamlit run app.py --logger.level debug
   ```

4. **Test Locally First:**
   ```bash
   streamlit run app.py
   # Should work on localhost before deploying
   ```

5. **Contact Support:**
   - Replit Community
   - Streamlit Community Forum
   - GitHub Issues

## Success Indicators

Your deployment is successful when:

✅ App loads in <10 seconds
✅ Health checks pass consistently
✅ All tabs are accessible
✅ File uploads work
✅ Downloads work
✅ No XSRF errors
✅ WebSocket connection stable
✅ Can generate proposals successfully
✅ No timeout errors
✅ Resource usage is reasonable

## Quick Fix Summary

| Issue | Quick Fix |
|---|---|
| XSRF Error | Set `enableXsrfProtection = false` |
| Health Check Timeout | Increase timeout to 60s, use lazy loading |
| Port Not Accessible | Bind to `0.0.0.0`, check firewall |
| CORS Error | Set `enableCORS = false` |
| Slow Startup | Use lazy loading, disable file watcher |
| WebSocket Failed | Enable compression, check browser |

---

**Last Updated:** 2025-01-16

For the latest deployment information, check:
- `.streamlit/config.toml` - Streamlit configuration
- `.replit` - Replit deployment settings
- `healthcheck.py` - Deployment verification
