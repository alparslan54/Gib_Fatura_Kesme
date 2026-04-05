package com.alparslan.gibapi.core;

import android.content.Context;
import android.net.Uri;
import android.os.Environment;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;

import okhttp3.ResponseBody;

public final class PdfSaver {

    private PdfSaver() {}

    // App-scoped Downloads: izin istemez
    public static File saveToDownloads(Context ctx, ResponseBody body, String fileName) throws IOException {
        if (body == null) throw new IOException("Empty body");
        if (fileName == null || fileName.trim().isEmpty()) fileName = "fatura.pdf";
        if (!fileName.toLowerCase().endsWith(".pdf")) fileName = fileName + ".pdf";

        File dir = ctx.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS);
        if (dir == null) dir = ctx.getFilesDir();
        if (!dir.exists() && !dir.mkdirs()) throw new IOException("Cannot create dir: " + dir.getAbsolutePath());

        File outFile = new File(dir, fileName);

        try (InputStream in = body.byteStream();
             FileOutputStream out = new FileOutputStream(outFile)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
            out.flush();
        }
        return outFile;
    }

    // PDF açmak için FileProvider URI
    public static Uri getUri(Context ctx, File file) {
        String authority = ctx.getPackageName() + ".fileprovider";
        return FileProvider.getUriForFile(ctx, authority, file);
    }
}
