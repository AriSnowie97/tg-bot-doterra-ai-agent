import { NavLink } from "react-router-dom";

import styles from "./Menu.module.css";
import { HomeSvg, ChatSvg, ArticlesSvg, ContactsSvg } from "../../assets/images";
import { useLang } from "../../contexts/LangContext";

const Menu = () => {
    const { t } = useLang();

    const navigation = [
        ["/", HomeSvg,"home", t("nav_home")],
        ["/chat", ChatSvg, "chat", t("nav_chat")],
        ["/articles", ArticlesSvg, "articles", t("nav_articles")],
        ["/contacts", ContactsSvg, "contacts", t("nav_contacts")]
    ]

    return (
        <>
            <menu>
                <nav className={styles.navigation}>
                    {navigation.map(([to, Svg, alt, name], index) => (
                        <NavLink
                        to={to}
                        key={index + 1}
                        className={({isActive}) => isActive ? styles.active : ""}>
                            {
                            Svg
                            ? <Svg className={styles.Svg} />
                            : <p>{alt}</p>
                            }
                            <h3>{name}</h3>
                        </NavLink>
                    ))}
                </nav>
            </menu>
        </>
    );
}

export {Menu};