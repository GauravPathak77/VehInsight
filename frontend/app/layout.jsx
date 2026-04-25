import "./globals.css";

export const metadata = {
  title: "VehInsight",
  description: "Vehicle logo, plate and color analyzer",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
