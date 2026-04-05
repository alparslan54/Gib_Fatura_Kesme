package com.alparslan.gibapi.core;

import android.content.Context;
import android.content.SharedPreferences;

public final class SessionManager {

    private static final String PREF = "gibapi_session";
    private static final String KEY_SESSION_ID = "session_id";
    private static final String KEY_BASE_URL = "base_url";

    private static SharedPreferences sp;

    private SessionManager() {}

    /** Uygulama açılışında (en az bir Activity'de) çağır */
    public static void init(Context ctx) {
        if (sp == null) {
            sp = ctx.getApplicationContext().getSharedPreferences(PREF, Context.MODE_PRIVATE);
        }
    }

    private static void ensureInit() {
        if (sp == null) {
            throw new IllegalStateException("SessionManager.init(context) çağrılmadı");
        }
    }

    public static void set(String id) {
        ensureInit();
        sp.edit().putString(KEY_SESSION_ID, id == null ? "" : id.trim()).apply();
    }

    public static String get() {
        ensureInit();
        String v = sp.getString(KEY_SESSION_ID, "");
        return v == null ? "" : v;
    }

    public static boolean exists() {
        ensureInit();
        String v = sp.getString(KEY_SESSION_ID, "");
        return v != null && !v.trim().isEmpty();
    }

    public static void clear() {
        ensureInit();
        sp.edit().remove(KEY_SESSION_ID).apply();
    }

    // BaseUrl’yi de saklayalım (Intent’e bağımlılık azalır)
    public static void setBaseUrl(String baseUrl) {
        ensureInit();
        String s = baseUrl == null ? "" : baseUrl.trim();
        if (!s.isEmpty() && !s.endsWith("/")) s += "/";
        sp.edit().putString(KEY_BASE_URL, s).apply();
    }

    public static String getBaseUrl() {
        ensureInit();
        String v = sp.getString(KEY_BASE_URL, "");
        return v == null ? "" : v;
    }

    public static void clearAll() {
        ensureInit();
        sp.edit().clear().apply();
    }
}
