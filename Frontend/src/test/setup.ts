"""Frontend test setup and global fixtures."""

# This file is imported by Jest before running tests
# It sets up the test environment

import os
os.environ['NODE_ENV'] = 'test'

# Mock browser APIs
global.localStorage = {
    getItem: lambda self, key: None,
    setItem: lambda self, key, value: None,
    removeItem: lambda self, key: None,
    clear: lambda self: None
}

# Mock window.matchMedia
global.matchMedia = lambda self, query: {
    matches: False,
    media: query,
    onchange: None,
    addListener: lambda self, fn: None,
    removeListener: lambda self, fn: None,
    addEventListener: lambda self, event, fn: None,
    removeEventListener: lambda self, event, fn: None,
    dispatchEvent: lambda self, event: False
}
