package com.alparslan.gibapi.dto;

public class SessionRequest {
    public Auth auth;

    // Retrofit / Gson için gerekli: no-arg constructor
    public SessionRequest() {}

    // Opsiyonel kolaylık: tek satırda oluşturmak istersen
    public SessionRequest(String username, String password) {
        this.auth = new Auth(username, password);
    }

    public static class Auth {
        public String username;
        public String password;

        // Gson için gerekli: no-arg constructor
        public Auth() {}

        public Auth(String u, String p) {
            this.username = u;
            this.password = p;
        }
    }
}
