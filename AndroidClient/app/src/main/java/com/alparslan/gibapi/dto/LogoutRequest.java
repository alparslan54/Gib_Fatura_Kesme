// com.alparslan.gibapi.dto.LogoutRequest
package com.alparslan.gibapi.dto;

public class LogoutRequest {
    public String session_id;

    public LogoutRequest(String session_id) {
        this.session_id = session_id;
    }
}
