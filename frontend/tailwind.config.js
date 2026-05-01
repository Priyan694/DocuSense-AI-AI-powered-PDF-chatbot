export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#10233a",
        mist: "#eef5ff",
        shell: "#f8fbff",
        coral: "#eb6a4b",
        moss: "#187f6d",
        gold: "#f4bf4f",
        sky: "#5f87ff",
        slate: "#5f7188",
      },
      boxShadow: {
        panel: "0 24px 80px rgba(16, 37, 66, 0.14)",
        float: "0 18px 46px rgba(16, 35, 58, 0.16)",
      },
      fontFamily: {
        display: ['"Space Grotesk"', "sans-serif"],
        body: ['"DM Sans"', "sans-serif"],
      },
    },
  },
  plugins: [],
};
