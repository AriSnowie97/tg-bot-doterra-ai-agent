const HomeSvg = ({className}) => {
    return (
        <>
            <svg 
            className={className}
            // width="30"
            // height="30"
            viewBox="0 0 24 24"
            fill="none"
            >
                <path
                d="M4 11l8-7 8 7"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                />
                <path
                d="M6 10v10h12V10"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
                />
            </svg>
        </>
    );
};

export {HomeSvg}