import styles from "./Home.module.css";

import { ChatLinkBtn } from "./components/LinkBtn/posterity/ChatLinkBtn";
import { ArticlesLinkBtn } from "./components/LinkBtn/posterity/ArticlesLinkBtn";
import { LinkArticleBtn } from "./components/LinkArticleBtn";

import { TelegramLinkBtn } from "./components/LinkBtn/posterity/TelegramLinkBtn";

const Home = () => {

    let tg = window.Telegram.WebApp; //
    console.log(tg); //
    

    return (
        <>
            <div className={styles.wrapper}>
                <div className={styles.introduction}>
                    <h1>Привіт! &#128075;</h1>
                    <p>Я допоможу підібрати ефірні олії, БАДи та набори doTERRA - просто запитай.</p>
                </div>
                <div className={styles.services}>
                    <ChatLinkBtn />
                    <ArticlesLinkBtn />
                </div>
                <div className={styles.popular}>
                    <h3>ПОПУЛЯРНЕ ЗАРАЗ</h3>
                    <div className={styles.articles}>
                        <LinkArticleBtn />
                        <LinkArticleBtn />
                        <LinkArticleBtn />
                        <LinkArticleBtn />
                        <LinkArticleBtn />
                        <LinkArticleBtn />
                        <LinkArticleBtn />
                    </div>
                </div>
                <div className={styles.links}>
                    <h3>НАШ ТЕЛЕГРАМ-КАНАЛ</h3>
                    <div className={styles.list}>
                        <TelegramLinkBtn />
                    </div>
                </div>
                <a className={styles.contact} href="" >Написати спеціалісту напряму <code>{"-->"}</code></a>
            </div>
        </>
    );
}

export {Home};