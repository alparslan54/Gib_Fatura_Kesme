package com.alparslan.gibapi.api;

import com.alparslan.gibapi.core.SessionManager;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

import okhttp3.Interceptor;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

public final class ApiClient {

    private static volatile OkHttpClient client;
    private static final Map<String, Retrofit> RETROFITS = new ConcurrentHashMap<>();

    private ApiClient() {}

    public static GibApi create(String baseUrl) {
        String normalized = normalizeBaseUrl(baseUrl);
        Retrofit r = RETROFITS.get(normalized);
        if (r == null) {
            Retrofit newRetrofit = new Retrofit.Builder()
                    .baseUrl(normalized)
                    .client(getClient())
                    .addConverterFactory(GsonConverterFactory.create())
                    .build();

            Retrofit existing = RETROFITS.putIfAbsent(normalized, newRetrofit);
            r = (existing != null) ? existing : newRetrofit;
        }
        return r.create(GibApi.class);
    }

    private static OkHttpClient getClient() {
        if (client == null) {
            synchronized (ApiClient.class) {
                if (client == null) {
                    OkHttpClient.Builder b = new OkHttpClient.Builder()
                            .connectTimeout(15, TimeUnit.SECONDS)
                            .readTimeout(60, TimeUnit.SECONDS)
                            .writeTimeout(60, TimeUnit.SECONDS)
                            .retryOnConnectionFailure(true);

                    // 1) Authorization: Bearer <session_id> otomatik ekle
                    b.addInterceptor(new Interceptor() {
                        @Override
                        public Response intercept(Chain chain) throws java.io.IOException {
                            Request original = chain.request();

                            // Session yoksa aynen devam
                            String sid = SessionManager.get();
                            if (sid == null || sid.trim().isEmpty()) {
                                return chain.proceed(original);
                            }

                            // Zaten header ekliyse overwrite etmeyelim
                            if (original.header("Authorization") != null) {
                                return chain.proceed(original);
                            }

                            Request withAuth = original.newBuilder()
                                    .header("Authorization", "Bearer " + sid)
                                    .build();

                            return chain.proceed(withAuth);
                        }
                    });

                    // 2) Logging: Token sızdırmasın diye header'ı redact et
                    HttpLoggingInterceptor log = new HttpLoggingInterceptor();
                    log.redactHeader("Authorization");
                    log.setLevel(HttpLoggingInterceptor.Level.BODY);
                    b.addInterceptor(log);

                    client = b.build();
                }
            }
        }
        return client;
    }

    public static String normalizeBaseUrl(String input) {
        if (input == null) return "http://127.0.0.1:8000/";
        String s = input.trim();
        if (s.isEmpty()) return "http://127.0.0.1:8000/";

        if (!s.startsWith("http://") && !s.startsWith("https://")) {
            s = "http://" + s;
        }
        if (!s.endsWith("/")) s = s + "/";
        return s;
    }
}
