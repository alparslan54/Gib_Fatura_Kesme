package com.alparslan.gibapi;

import android.app.Application;
import com.alparslan.gibapi.core.SessionManager;

public class App extends Application {
    @Override
    public void onCreate() {
        super.onCreate();
        SessionManager.init(this);
    }
}
