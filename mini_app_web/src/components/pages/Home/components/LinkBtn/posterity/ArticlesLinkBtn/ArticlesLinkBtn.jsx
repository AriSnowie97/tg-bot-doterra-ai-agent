import styles from "./ArticlesLinkBtn.module.css";
import { LinkBtn } from "../../LinkBtn";
import { ArticlesSvg } from "../../../../../../../assets/icons";


const ArticlesLinkBtn = () => {
    return (
        <>
            <LinkBtn 
            linkTo={"/articles"}
            Svg={ArticlesSvg}
            subject="articles"
            newStyles={styles}/>
        </>
    );
}

export {ArticlesLinkBtn};