package com.alparslan.gibapi.ui;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;

import com.alparslan.gibapi.R;
import com.alparslan.gibapi.api.ApiClient;
import com.alparslan.gibapi.api.GibApi;
import com.alparslan.gibapi.core.SessionManager;
import com.alparslan.gibapi.dto.SessionRequest;
import com.alparslan.gibapi.dto.SessionResponse;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class LoginActivity extends AppCompatActivity {

    private EditText etBaseUrl, etUsername, etPassword;
    private Button btnLogin,btnForceLogin;


    private ProgressBar progress;

    @Override
    protected void onCreate(Bundle savedInstanceState) {


        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);
        SessionManager.init(getApplicationContext());

        etBaseUrl = findViewById(R.id.et_base_url);
        etUsername = findViewById(R.id.et_username);
        etPassword = findViewById(R.id.et_password);
        btnLogin  = findViewById(R.id.btn_login);
        btnForceLogin = findViewById(R.id.btn_force_login);
        progress  = findViewById(R.id.progress);

        etBaseUrl.setText("http://##############/");

        btnLogin.setOnClickListener(v -> doLogin());
        btnForceLogin.setOnClickListener(v -> doForceLogin());
    }

    private void doLogin() {
        String baseUrl = normalizeBaseUrl(etBaseUrl.getText().toString().trim());
        String username = etUsername.getText().toString().trim();
        String password = etPassword.getText().toString();

        if (baseUrl.isEmpty()) {
            toast("Base URL boş olamaz");
            return;
        }
        if (username.isEmpty() || password.isEmpty()) {
            toast("Kullanıcı adı ve şifre gerekli");
            return;
        }

        progress.setVisibility(View.VISIBLE);
        btnLogin.setEnabled(false);

        GibApi api = ApiClient.create(baseUrl);

        SessionRequest req = new SessionRequest();
        req.auth = new SessionRequest.Auth();
        req.auth.username = username;
        req.auth.password = password;

        api.createSession(req).enqueue(new Callback<SessionResponse>() {
            @Override
            public void onResponse(Call<SessionResponse> call, Response<SessionResponse> resp) {
                progress.setVisibility(View.GONE);
                btnLogin.setEnabled(true);

                if (!resp.isSuccessful() || resp.body() == null) {
                    toast("Login başarısız (HTTP " + resp.code() + ")");
                    return;
                }

                if (resp.body().session_id == null || resp.body().session_id.trim().isEmpty()) {
                    toast("Session alınamadı");
                    return;
                }

                SessionManager.set(resp.body().session_id);
                SessionManager.setBaseUrl(baseUrl);

                android.util.Log.i("GIBAPI", "LOGIN OK session_id=***" );

                Intent i = new Intent(LoginActivity.this, InvoiceActivity.class);
                i.putExtra("baseUrl", baseUrl);
                startActivity(i);
                finish(); // Login ekranına geri dönmeyi engeller

            }

            @Override
            public void onFailure(Call<SessionResponse> call, Throwable t) {
                progress.setVisibility(View.GONE);
                btnLogin.setEnabled(true);
                toast("Bağlantı hatası: " + t.getMessage());
            }
        });
    }

    private void doForceLogin() {
        String baseUrl = normalizeBaseUrl(etBaseUrl.getText().toString().trim());
        String username = etUsername.getText().toString().trim();
        String password = etPassword.getText().toString();

        if (baseUrl.isEmpty() || username.isEmpty() || password.isEmpty()) {
            toast("Base URL / kullanıcı / şifre boş olamaz");
            return;
        }

        progress.setVisibility(View.VISIBLE);
        btnLogin.setEnabled(false);
        btnForceLogin.setEnabled(false);

        GibApi api = ApiClient.create(baseUrl);

        SessionRequest req = new SessionRequest(username, password);

        api.forceSession(req).enqueue(new Callback<SessionResponse>() {
            @Override
            public void onResponse(Call<SessionResponse> call,
                                   Response<SessionResponse> resp) {

                progress.setVisibility(View.GONE);
                btnLogin.setEnabled(true);
                btnForceLogin.setEnabled(true);

                if (!resp.isSuccessful() || resp.body() == null
                        || resp.body().session_id == null) {
                    toast("Zorla giriş başarısız");
                    return;
                }

                SessionManager.setBaseUrl(baseUrl);
                SessionManager.set(resp.body().session_id);

                Intent i = new Intent(LoginActivity.this, InvoiceActivity.class);
                i.putExtra("baseUrl", baseUrl);
                startActivity(i);
                finish();
            }

            @Override
            public void onFailure(Call<SessionResponse> call, Throwable t) {
                progress.setVisibility(View.GONE);
                btnLogin.setEnabled(true);
                btnForceLogin.setEnabled(true);
                toast("Bağlantı hatası: " + t.getMessage());
            }
        });
    }


    private String normalizeBaseUrl(String input) {
        if (input == null) return "";
        String s = input.trim();
        if (s.isEmpty()) return "";
        if (!s.startsWith("http://") && !s.startsWith("https://")) s = "http://" + s;
        if (!s.endsWith("/")) s = s + "/";
        return s;
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
    }



}
