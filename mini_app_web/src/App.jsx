import "./App.css";
import styles from "./App.module.css";
import { Router } from "./Router";
import { Header } from "./components/Header";
import { Menu } from "./components/Menu";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

function getTelegramStartParam() {
  try {
    const sdkParam = window.Telegram?.WebApp?.initDataUnsafe?.start_param;
    if (sdkParam) return sdkParam;
  } catch (e) {
    // ignore
  }

  try {
    const searchParams = new URLSearchParams(window.location.search);
    const searchParam = searchParams.get("tgWebAppStartParam");
    if (searchParam) return searchParam;
  } catch (e) {
    // ignore
  }

  try {
    const hash = window.location.hash || "";
    if (hash.includes("tgWebAppStartParam=")) {
      const match = hash.match(/tgWebAppStartParam=([^&]+)/);
      if (match) return decodeURIComponent(match[1]);
    }
  } catch (e) {
    // ignore
  }

  return null;
}

function App() {
  const navigate = useNavigate();

  useEffect(() => {
    // Підтримка прямих посилань Telegram Mini App (t.me/<bot>/app?startapp=article_slug)
    const startParam = getTelegramStartParam();
    if (startParam) {
      if (startParam.startsWith("article_")) {
        const slug = startParam.replace(/^article_/, "");
        navigate(`/article/${slug}`);
        return;
      }
      if (startParam === "chat") {
        navigate("/chat");
        return;
      }
      if (startParam === "articles") {
        navigate("/articles");
        return;
      }
      if (startParam === "contacts") {
        navigate("/contacts");
        return;
      }
      navigate(`/article/${startParam}`);
      return;
    }

    // Якщо відкрили за конкретним посиланням (наприклад, стаття), не скидаємо на Головну.
    // Якщо хеш порожній або просто '#/', переходимо на Головну (щоб скинути кеш телеграму, якщо він відкриває стару сторінку).
    if (!window.location.hash || window.location.hash === '#/' || window.location.hash === '') {
      navigate("/");
    }
  }, [navigate]);

  return (
    <>
      <div className={styles.wrapAll}>
        <Header />
        <div className={styles.appWrapper}>
          <Router />
        </div>
          <Menu />
      </div>
    </>
  );
}

export default App;