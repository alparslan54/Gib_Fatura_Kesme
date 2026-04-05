package com.alparslan.gibapi.ui;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.MediaStore;
import android.util.Log;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;

import com.alparslan.gibapi.core.PdfSaver;
import com.alparslan.gibapi.R;
import com.alparslan.gibapi.api.ApiClient;
import com.alparslan.gibapi.api.GibApi;
import com.alparslan.gibapi.core.SessionManager;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;

import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ResultActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        setContentView(R.layout.activity_result);
        SessionManager.init(getApplicationContext());

        String uuid = getIntent().getStringExtra("uuid");
        String status = getIntent().getStringExtra("status");
        String smsErr = getIntent().getStringExtra("sms_error");

        TextView tvStatus = findViewById(R.id.tvstatus);
        TextView tvUuid = findViewById(R.id.tvuuid);
        TextView tvSms = findViewById(R.id.tvsms);
        Button btnLogout = findViewById(R.id.btn_logout);
        Button btnDownloadPdf = findViewById(R.id.btn_download_pdf);

        tvStatus.setText("Durum: " + (status == null ? "-" : status));
        tvUuid.setText("UUID: " + (uuid == null ? "-" : uuid));
        tvSms.setText("SMS: " + (smsErr == null || smsErr.isEmpty() ? "-" : ("Hata: " + smsErr)));

        // UUID yoksa PDF butonu kapalı
        if (uuid == null || uuid.trim().isEmpty()) {
            btnDownloadPdf.setEnabled(false);
        }

        btnDownloadPdf.setOnClickListener(v -> downloadAndOpenPdf(uuid));

        btnLogout.setOnClickListener(v -> {
            String baseUrl = getIntent().getStringExtra("baseUrl");
            if (baseUrl == null || baseUrl.trim().isEmpty()) {
                baseUrl = SessionManager.getBaseUrl();
            }
            if (baseUrl == null) baseUrl = "";
            if (!baseUrl.endsWith("/")) baseUrl += "/";

            // Bearer interceptor kullanıyoruz. SessionManager.get() sadece local kontrol için.
            String sid = SessionManager.get();

            // 1) BACKEND LOGOUT ÇAĞRISI (body yok, sid query/body yok)
            // Session yoksa zaten backend 401 döner; bu normal. Biz local session’ı her halükarda sileceğiz.
            if (sid == null || sid.isEmpty()) {
                SessionManager.clearAll();
                Intent i = new Intent(ResultActivity.this, LoginActivity.class);
                i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                startActivity(i);
                finish();
                return;
            }
            GibApi api = ApiClient.create(baseUrl);
            api.logout().enqueue(new retrofit2.Callback<Void>() {
                @Override
                public void onResponse(retrofit2.Call<Void> call, retrofit2.Response<Void> response) {
                    Log.i("GIBAPI", "Backend logout OK " + response.code());
                    SessionManager.clearAll();

                    Intent i = new Intent(ResultActivity.this, LoginActivity.class);
                    i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                    startActivity(i);
                    finish();
                }

                @Override
                public void onFailure(retrofit2.Call<Void> call, Throwable t) {
                    Log.e("GIBAPI", "Backend logout FAIL: " + t.getMessage());
                    // Yine de local temizle ve login’e dön (kullanıcı app’te takılı kalmasın)
                    SessionManager.clearAll();

                    Intent i = new Intent(ResultActivity.this, LoginActivity.class);
                    i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
                    startActivity(i);
                    finish();
                }
                });


            // 2) LOCAL SESSION SİL

        });
    }

    private void downloadAndOpenPdf(String uuid) {
        String baseUrl = getIntent().getStringExtra("baseUrl");
        if (baseUrl == null || baseUrl.trim().isEmpty()) {
            baseUrl = SessionManager.getBaseUrl();
        }
        if (baseUrl == null) baseUrl = "";
        if (!baseUrl.endsWith("/")) baseUrl += "/";

        // Bearer interceptor zaten Authorization ekliyor.
        // Burada sid kontrolü yaparsan “session var ama boş görünür / edge-case” durumlarında gereksiz bloklarsın.
        if (uuid == null || uuid.trim().isEmpty()) {
            Toast.makeText(this, "UUID yok.", Toast.LENGTH_LONG).show();
            return;
        }

        Toast.makeText(this, "PDF indiriliyor...", Toast.LENGTH_SHORT).show();


        GibApi api = ApiClient.create(baseUrl);
        api.downloadPdf(uuid).enqueue(new Callback<ResponseBody>() {
            @Override
            public void onResponse(Call<ResponseBody> call, Response<ResponseBody> res) {
                if (res.code() == 401) {
                    Toast.makeText(ResultActivity.this,
                            "Oturum süresi doldu. Tekrar giriş yap.",
                            Toast.LENGTH_LONG).show();
                    // İstersen direkt Login’e de atabilirsin:
                    // goLogin();
                    return;
                }

                if (!res.isSuccessful() || res.body() == null) {
                    Toast.makeText(ResultActivity.this,
                            "PDF indirilemedi: HTTP " + res.code(),
                            Toast.LENGTH_LONG).show();
                    return;
                }

                try {
                    Uri pdfUri = savePdfToPublicDownloads(res.body(), "fatura-" + uuid + ".pdf");
                    openPdf(pdfUri);
                } catch (Exception e) {
                    Log.e("GIBAPI", "PDF save/open error", e);
                    Toast.makeText(ResultActivity.this,
                            "PDF kaydetme hatası: " + e.getMessage(),
                            Toast.LENGTH_LONG).show();
                }
            }

            @Override
            public void onFailure(Call<ResponseBody> call, Throwable t) {
                Toast.makeText(ResultActivity.this,
                        "PDF indirme hatası: " + t.getMessage(),
                        Toast.LENGTH_LONG).show();
            }
        });
    }

    private File savePdfToAppDownloads(ResponseBody body, String filename) throws Exception {
        // /Android/data/<package>/files/Download/
        File dir = getExternalFilesDir(android.os.Environment.DIRECTORY_DOWNLOADS);
        if (dir == null) dir = getFilesDir();
        if (!dir.exists() && !dir.mkdirs()) throw new Exception("Klasör oluşturulamadı: " + dir);

        File outFile = new File(dir, filename);

        try (InputStream in = body.byteStream();
             FileOutputStream out = new FileOutputStream(outFile)) {
            byte[] buf = new byte[8192];
            int r;
            while ((r = in.read(buf)) != -1) out.write(buf, 0, r);
            out.flush();
        }
        return outFile;
    }

    private void handleFinalLogout() {
        SessionManager.clearAll();
        goToLogin();
    }

    private void goToLogin() {
        Intent i = new Intent(this, LoginActivity.class);
        i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
        startActivity(i);
        finish();
    }

    private void openPdf(Uri uri) {
        Intent intent = new Intent(Intent.ACTION_VIEW);
        intent.setDataAndType(uri, "application/pdf");
        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);

        try {
            startActivity(intent);
        } catch (Exception e) {
            Toast.makeText(this,
                    "PDF açacak uygulama bulunamadı.",
                    Toast.LENGTH_LONG).show();
        }
    }


    private Uri savePdfToPublicDownloads(ResponseBody body, String filename) throws Exception {

        ContentValues values = new ContentValues();
        values.put(MediaStore.Downloads.DISPLAY_NAME, filename);
        values.put(MediaStore.Downloads.MIME_TYPE, "application/pdf");

        // Android 10+ için
        values.put(MediaStore.Downloads.IS_PENDING, 1);

        ContentResolver resolver = getContentResolver();
        Uri collection = null;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            collection = MediaStore.Downloads.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY);
        }

        Uri fileUri = resolver.insert(collection, values);
        if (fileUri == null) throw new Exception("MediaStore insert failed");

        try (InputStream in = body.byteStream();
             OutputStream out = resolver.openOutputStream(fileUri)) {

            if (out == null) throw new Exception("OutputStream null");

            byte[] buf = new byte[8192];
            int r;
            while ((r = in.read(buf)) != -1) {
                out.write(buf, 0, r);
            }
            out.flush();
        }

        // Yazma tamamlandı
        values.clear();
        values.put(MediaStore.Downloads.IS_PENDING, 0);
        resolver.update(fileUri, values, null, null);

        return fileUri;
    }


    // İstersen 401’de direkt login’e dönmek için kullanırsın:
    // private void goLogin() {
    //     Intent i = new Intent(ResultActivity.this, LoginActivity.class);
    //     i.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TASK);
    //     startActivity(i);
    //     finish();
    // }
}
