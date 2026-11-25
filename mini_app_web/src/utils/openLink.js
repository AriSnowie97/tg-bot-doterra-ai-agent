/**
 * Відкриває зовнішні посилання коректно всередині Telegram Mini App (iOS / Android / Desktop)
 * та у звичайному браузері.
 */
export const isExternalUrl = (url) =>
  typeof url === "string" && /^https?:\/\//i.test(url.trim());

export const openExternalLink = (url) => {
  if (!url) return;
  const cleanUrl = url.trim();
  const tg = window.Telegram?.WebApp;

  try {
    if (/^https?:\/\/(t\.me|telegram\.me)\//i.test(cleanUrl)) {
      if (tg?.openTelegramLink) {
        tg.openTelegramLink(cleanUrl);
        return;
      }
    } else if (tg?.openLink) {
      tg.openLink(cleanUrl);
      return;
    }
  } catch (err) {
    console.warn("Telegram WebApp link open failed, falling back:", err);
  }

  window.open(cleanUrl, "_blank", "noopener,noreferrer");
};
