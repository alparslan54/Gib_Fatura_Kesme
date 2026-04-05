package com.alparslan.gibapi.api;

import com.alparslan.gibapi.dto.FullProcessRequest;
import com.alparslan.gibapi.dto.FullProcessResponse;
import com.alparslan.gibapi.dto.SessionRequest;
import com.alparslan.gibapi.dto.SessionResponse;

import okhttp3.ResponseBody;
import retrofit2.Call;
import retrofit2.http.Body;
import retrofit2.http.GET;
import retrofit2.http.POST;
import retrofit2.http.Path;

public interface GibApi {

    @POST("/api/v1/session")
    Call<SessionResponse> createSession(@Body SessionRequest body);

    @POST("/api/v1/session/force")
    Call<SessionResponse> forceSession(@Body SessionRequest body);

    @POST("/api/v1/full-process")
    Call<FullProcessResponse> createInvoice(@Body FullProcessRequest body);

    // Backend'i Bearer'a çevirdiysek: body yok
    @POST("/api/v1/logout")
    Call<Void> logout();

    @GET("/api/v1/download-pdf/{uuid}")
    Call<ResponseBody> downloadPdf(@Path("uuid") String uuid);
}
