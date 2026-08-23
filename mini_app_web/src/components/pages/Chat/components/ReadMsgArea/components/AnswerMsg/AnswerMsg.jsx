import { Link } from "react-router-dom";
import styles from "./AnswerMsg.module.css";


/**
 * Парсить текст відповіді LLM і замінює markdown-посилання
 * формату [Текст кнопки](chunk_id) на інтерактивні кнопки.
 * Зовнішні URL (http/https) відкриваються у браузері,
 * внутрішні chunk_id — ведуть на /article/:slug.
 */
const parseAnswerWithLinks = (text) => {
    // Шукаємо всі [текст](посилання)
    const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = linkRegex.exec(text)) !== null) {
        // Текст до посилання
        if (match.index > lastIndex) {
            parts.push({
                type: "text",
                content: text.slice(lastIndex, match.index),
            });
        }

        const label = match[1];
        const href = match[2];
        const isExternal = href.startsWith("http://") || href.startsWith("https://");

        parts.push({
            type: "link",
            label,
            href,
            isExternal,
        });

        lastIndex = match.index + match[0].length;
    }

    // Залишок тексту після останнього посилання
    if (lastIndex < text.length) {
        parts.push({ type: "text", content: text.slice(lastIndex) });
    }

    return parts;
};


const AnswerMsg = ({ answer }) => {
    const parts = parseAnswerWithLinks(answer);

    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.msgWrap}>
                    <p style={{ whiteSpace: "pre-wrap" }}>
                        {parts.map((part, i) => {
                            if (part.type === "text") {
                                return <span key={i}>{part.content}</span>;
                            }
                            if (part.isExternal) {
                                return (
                                    <a
                                        key={i}
                                        href={part.href}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className={styles.sourceBtn}
                                    >
                                        {part.label}
                                    </a>
                                );
                            }
                            // Внутрішній chunk_id → навігація до статті
                            return (
                                <Link
                                    key={i}
                                    to={`/article/${part.href}`}
                                    className={styles.sourceBtn}
                                >
                                    {part.label}
                                </Link>
                            );
                        })}
                    </p>
                </div>
            </div>
        </>
    );
};

export { AnswerMsg };