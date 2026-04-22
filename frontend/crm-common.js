(function() {
  function getApiBase() {
    var saved = localStorage.getItem('crm_api_base');
    if (saved) {
      return saved.replace(/\/$/, '');
    }

    if (window.location.protocol === 'file:' || ['localhost', '127.0.0.1'].indexOf(window.location.hostname) !== -1) {
      return 'http://127.0.0.1:8000';
    }

    return window.location.origin.replace(/\/$/, '');
  }

  function getToken() {
    return localStorage.getItem('crm_token') || '';
  }

  function getCurrentUser() {
    var raw = localStorage.getItem('crm_user');
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw);
    } catch (error) {
      return null;
    }
  }

  function isAdmin(user) {
    return !!user && (user.is_admin === true || user.username === 'admin');
  }

  function isAuthenticated() {
    return !!getCurrentUser() && !!getToken();
  }

  function clearAuth() {
    localStorage.removeItem('crm_user');
    localStorage.removeItem('crm_token');
    localStorage.removeItem('crm_api_base');
    sessionStorage.removeItem('crm_scoring_options');
  }

  function getDefaultPage(user) {
    return isAdmin(user || getCurrentUser()) ? 'page-report.html' : 'page-opportunities.html';
  }

  function redirectToLogin() {
    window.location.href = 'login.html';
  }

  function redirectToDefault(user) {
    window.location.href = getDefaultPage(user);
  }

  function setAuthSession(user, token, apiBase) {
    localStorage.setItem('crm_user', JSON.stringify({
      id: user.id,
      username: user.username,
      is_admin: user.is_admin === true,
      loginTime: new Date().toISOString()
    }));
    localStorage.setItem('crm_token', token);
    if (apiBase) {
      localStorage.setItem('crm_api_base', apiBase.replace(/\/$/, ''));
    }
  }

  function requireAuth(permissionKey) {
    var user = getCurrentUser();
    if (!user || !getToken()) {
      clearAuth();
      redirectToLogin();
      return null;
    }

    if (permissionKey === 'user_management' && !isAdmin(user)) {
      alert('只有管理员账号可以访问该页面。');
      window.location.href = 'page-opportunities.html';
      return null;
    }

    return user;
  }

  async function apiRequest(path, options) {
    var opts = options ? Object.assign({}, options) : {};
    var headers = Object.assign({}, opts.headers || {});
    var body = opts.body;

    if (body && !(body instanceof FormData) && typeof body === 'object') {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }

    if (getToken()) {
      headers.Authorization = 'Bearer ' + getToken();
    }

    opts.headers = headers;
    opts.body = body;

    var response = await fetch(getApiBase() + path, opts);
    var payload = null;
    var text = '';

    if (response.status !== 204) {
      text = await response.text();
      if (text) {
        try {
          payload = JSON.parse(text);
        } catch (error) {
          payload = { message: text };
        }
      }
    }

    if (!response.ok) {
      var message = payload && (payload.detail || payload.message) ? (payload.detail || payload.message) : '请求失败';
      if (response.status === 401) {
        clearAuth();
        redirectToLogin();
      }
      throw new Error(message);
    }

    return payload;
  }

  async function getScoringOptions(forceRefresh) {
    if (!forceRefresh) {
      var cached = sessionStorage.getItem('crm_scoring_options');
      if (cached) {
        try {
          return JSON.parse(cached);
        } catch (error) {
          sessionStorage.removeItem('crm_scoring_options');
        }
      }
    }

    var payload = await apiRequest('/api/scoring/options');
    sessionStorage.setItem('crm_scoring_options', JSON.stringify(payload || {}));
    return payload;
  }

  function canEditOwner(user, ownerId) {
    if (!user) {
      return false;
    }
    if (isAdmin(user)) {
      return true;
    }
    return String(user.id) === String(ownerId || '');
  }

  function escapeHtml(value) {
    var div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
  }

  window.CRMApp = {
    apiRequest: apiRequest,
    getScoringOptions: getScoringOptions,
    canEditOwner: canEditOwner,
    escapeHtml: escapeHtml,
    getApiBase: getApiBase,
    getCurrentUser: getCurrentUser,
    getDefaultPage: getDefaultPage,
    getToken: getToken,
    isAuthenticated: isAuthenticated,
    isAdmin: isAdmin,
    clearAuth: clearAuth,
    redirectToDefault: redirectToDefault,
    redirectToLogin: redirectToLogin,
    requireAuth: requireAuth,
    setAuthSession: setAuthSession
  };
})();
