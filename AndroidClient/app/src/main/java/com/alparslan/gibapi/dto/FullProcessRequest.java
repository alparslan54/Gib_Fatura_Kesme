package com.alparslan.gibapi.dto;

public class FullProcessRequest {

    public Fatura fatura;

    public static class Fatura {
        public String vkn;
        public String alici_unvan;
        public String urun_adi;
        public int miktar;
        public double birim_fiyat;
        public Integer kdv_orani;
    }
}
