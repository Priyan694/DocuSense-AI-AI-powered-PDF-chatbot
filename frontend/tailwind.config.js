export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#102542",
        mist: "#eef3f8",
        coral: "#f87060",
        moss: "#557c55",
        gold: "#f4b860",
      },
      boxShadow: {
        panel: "0 24px 80px rgba(16, 37, 66, 0.14)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
        body: ['"DM Sans"', "sans-serif"],
      },
    },
  },
  plugins: [],
};

