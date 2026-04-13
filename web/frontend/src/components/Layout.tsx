import { ReactNode } from "react";
import { Outlet } from "react-router-dom";
import Navbar from "./Navbar";

export default function Layout({ children }: { children?: ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">{children ?? <Outlet />}</main>
    </div>
  );
}
