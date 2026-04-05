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
import com.alparslan.gibapi.dto.FullProcessRequest;
import com.alparslan.gibapi.dto.FullProcessResponse;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class InvoiceActivity extends AppCompatActivity {

    private EditText etVkn, etUnvan, etUrun, etMiktar, etBirimFiyat, etKdv;
    private Button btnCreate;
    private ProgressBar progress;

    private String baseUrl;

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_invoice);
        SessionManager.init(getApplicationContext());

        baseUrl = getIntent().getStringExtra("baseUrl");
        if (baseUrl == null || baseUrl.trim().isEmpty()) {
            baseUrl = SessionManager.getBaseUrl();
        }
        if (baseUrl == null) baseUrl = "";
        if (!baseUrl.endsWith("/")) baseUrl = baseUrl + "/";




        if (!SessionManager.exists()) {
            Intent i = new Intent(this, LoginActivity.class);
            i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            startActivity(i);
            finish();
            return;
        }


        etVkn = findViewById(R.id.etVkn);
        etUnvan = findViewById(R.id.etUnvan);
        etUrun = findViewById(R.id.etUrun);
        etMiktar = findViewById(R.id.etMiktar);
        etBirimFiyat = findViewById(R.id.etbirimfiyat);
        etKdv = findViewById(R.id.etkdv);

        btnCreate = findViewById(R.id.btncreate);
        progress = findViewById(R.id.progress);

        btnCreate.setOnClickListener(v -> createInvoice());
    }


    private void createInvoice() {

        android.util.Log.i("GIBAPI", "INVOICE create pressed. session_exists=" + SessionManager.exists());


        // GEÇİCİ: session kontrolünü kapattık (debug için)
        if (!SessionManager.exists()) {
            toast("Session yok. Tekrar giriş yap.");
            Intent i = new Intent(this, LoginActivity.class);
            i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
            startActivity(i);
            finish();
            return;
        }


        String vkn = etVkn.getText().toString().trim();
        String unvan = etUnvan.getText().toString().trim();
        String urun = etUrun.getText().toString().trim();

        if (vkn.isEmpty() || unvan.isEmpty() || urun.isEmpty()) {
            toast("VKN/Ünvan/Ürün alanları zorunlu");
            return;
        }

        int miktar;
        double fiyat;
        Integer kdv = 20;

        try {
            String mStr = etMiktar.getText().toString().trim();
            String fStr = etBirimFiyat.getText().toString().trim();

            if (mStr.isEmpty() || fStr.isEmpty()) {
                toast("Miktar ve birim fiyat zorunlu");
                return;
            }

            miktar = Integer.parseInt(mStr);
            fiyat = Double.parseDouble(fStr);

            String kStr = etKdv.getText().toString().trim();
            if (!kStr.isEmpty()) kdv = Integer.parseInt(kStr);

        } catch (Exception e) {
            toast("Miktar/BirimFiyat/KDV formatı hatalı");
            return;
        }

        progress.setVisibility(View.VISIBLE);
        btnCreate.setEnabled(false);

        GibApi api = ApiClient.create(baseUrl);

        FullProcessRequest req = new FullProcessRequest();
        req.fatura = new FullProcessRequest.Fatura();
        req.fatura.vkn = vkn;
        req.fatura.alici_unvan = unvan;
        req.fatura.urun_adi = urun;
        req.fatura.miktar = miktar;
        req.fatura.birim_fiyat = fiyat;
        req.fatura.kdv_orani = kdv;

        api.createInvoice(req).enqueue(new Callback<FullProcessResponse>() {
            @Override
            public void onResponse(Call<FullProcessResponse> call, Response<FullProcessResponse> resp) {
                progress.setVisibility(View.GONE);
                btnCreate.setEnabled(true);

                if (resp.code() == 401) {
                    toast("Oturum süresi doldu. Tekrar giriş yapın.");
                    //goLogin();
                    return;
                }

                if (!resp.isSuccessful() || resp.body() == null) {
                    toast("Fatura başarısız (HTTP " + resp.code() + ")");
                    return;
                }

                FullProcessResponse body = resp.body();

                if (body.fatura_uuid == null || body.fatura_uuid.trim().isEmpty()) {
                    toast("UUID gelmedi. Backend log kontrol et.");
                    return;
                }

                Intent i = new Intent(InvoiceActivity.this, ResultActivity.class);
                i.putExtra("uuid", body.fatura_uuid);
                startActivity(i);
                finish();
            }

            @Override
            public void onFailure(Call<FullProcessResponse> call, Throwable t) {
                progress.setVisibility(View.GONE);
                btnCreate.setEnabled(true);
                toast("Bağlantı hatası: " + t.getMessage());
            }
        });

    }

    private void toast(String s) {
        Toast.makeText(this, s, Toast.LENGTH_LONG).show();
    }
}
