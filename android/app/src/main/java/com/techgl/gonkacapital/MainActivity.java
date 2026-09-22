package com.techgl.gonkacapital;

import android.app.Activity;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Insets;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.view.WindowManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * Gonka Capital is a web app in a WebView. The app itself lives in assets/www and works
 * offline from the data bundled with the build; it fetches a newer data file when
 * the phone is online. Links to filings open in the phone's browser, never in here.
 *
 * Android 15 (API 35) draws every app edge to edge whether it asks to or not, so the
 * page runs under the status bar and the gesture bar. Rather than opt out, the page
 * is told how tall those bars are and keeps its own header and tab bar clear of them,
 * which also lets the app's colours run all the way to the edges of the screen.
 */
public class MainActivity extends Activity {

    private WebView web;
    private String insetCss = "";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        boolean night = (getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)
                == Configuration.UI_MODE_NIGHT_YES;

        web = new WebView(this);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);   // localStorage holds the last downloaded feed
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setTextZoom(100);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
                Uri u = req.getUrl();
                String scheme = u.getScheme();
                if ("http".equals(scheme) || "https".equals(scheme)) {
                    startActivity(new Intent(Intent.ACTION_VIEW, u));
                    return true;
                }
                return false;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                // Insets usually arrive before the document exists, so re-apply them here.
                applyInsets();
            }
        });

        web.setOnApplyWindowInsetsListener((v, insets) -> {
            insetCss = buildInsetCss(insets);
            applyInsets();
            return insets;
        });

        web.setBackgroundColor(night ? Color.parseColor("#121316") : Color.parseColor("#F6F5F1"));
        setContentView(web);

        // After setContentView: the decor view, and so the insets controller, exist only now.
        goEdgeToEdge(night);

        web.loadUrl("file:///android_asset/www/index.html");
    }

    /** Lay out behind the system bars on every version, and match the icon colour to the theme. */
    private void goEdgeToEdge(boolean night) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController c = getWindow().getDecorView().getWindowInsetsController();
            if (c != null) {
                // Dark icons on the light theme, light icons on the dark one.
                int light = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS
                        | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                c.setSystemBarsAppearance(night ? 0 : light, light);
            }
        } else {
            int flags = View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                    | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN;
            if (!night) {
                flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            }
            getWindow().getDecorView().setSystemUiVisibility(flags);
        }
        // The bars are painted by the page underneath them.
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_DRAWS_SYSTEM_BAR_BACKGROUNDS);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);
    }

    private String buildInsetCss(WindowInsets insets) {
        int top, bottom, left, right;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Insets bars = insets.getInsets(
                    WindowInsets.Type.systemBars() | WindowInsets.Type.displayCutout());
            top = bars.top; bottom = bars.bottom; left = bars.left; right = bars.right;
        } else {
            top = insets.getSystemWindowInsetTop();
            bottom = insets.getSystemWindowInsetBottom();
            left = insets.getSystemWindowInsetLeft();
            right = insets.getSystemWindowInsetRight();
        }
        float d = getResources().getDisplayMetrics().density;
        return "(function(r){"
                + "r.style.setProperty('--inset-top','" + px(top, d) + "');"
                + "r.style.setProperty('--inset-bottom','" + px(bottom, d) + "');"
                + "r.style.setProperty('--inset-left','" + px(left, d) + "');"
                + "r.style.setProperty('--inset-right','" + px(right, d) + "');"
                + "})(document.documentElement);";
    }

    private static String px(int raw, float density) {
        return Math.round(raw / density) + "px";
    }

    private void applyInsets() {
        if (web != null && !insetCss.isEmpty()) {
            web.evaluateJavascript(insetCss, null);
        }
    }

    @Override
    public void onBackPressed() {
        // In-app navigation is hash based, so history walks the screens.
        if (web.canGoBack()) {
            web.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
