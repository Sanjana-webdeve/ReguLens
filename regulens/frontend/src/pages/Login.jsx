import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth } from "../auth.jsx";
import { Notice } from "../components/ui.jsx";

export default function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login"); // login | register | forgot | reset
  const [f, setF] = useState({ email: "", password: "", full_name: "", token: "" });
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  if (user) return <Navigate to="/" replace />;
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setInfo("");
    try {
      if (mode === "login") { await login(f.email, f.password); nav("/"); }
      else if (mode === "register") {
        await api.post("/auth/register", { email: f.email, password: f.password, full_name: f.full_name });
        await login(f.email, f.password); nav("/");
      } else if (mode === "forgot") {
        const r = await api.post("/auth/forgot-password", { email: f.email });
        setInfo(r.data.message);
        if (r.data.reset_token) { setF({ ...f, token: r.data.reset_token, password: "" }); setMode("reset"); setInfo("Development mode: reset token filled in below. Choose a new password."); }
      } else {
        await api.post("/auth/reset-password", { token: f.token, new_password: f.password });
        setMode("login"); setInfo("Password updated. Log in with your new password.");
      }
    } catch (e) { setErr(errMsg(e)); }
  };

  const titles = { login: "Log in", register: "Create account", forgot: "Reset your password", reset: "Choose a new password" };
  return (
    <div className="login">
      <div className="login-art">
        <h1>ReguLens</h1>
        <p>Upload a regulation. Ask what it requires. Check your policy against it. Hand an auditor the evidence.</p>
      </div>
      <form className="login-card" onSubmit={submit}>
        <h2>{titles[mode]}</h2>
        <Notice kind="error">{err}</Notice>
        <Notice kind="ok">{info}</Notice>
        {mode === "register" && <label>Full name<input required value={f.full_name} onChange={set("full_name")} /></label>}
        {mode !== "reset" && <label>Email<input type="email" required value={f.email} onChange={set("email")} /></label>}
        {mode === "reset" && <label>Reset token<input required value={f.token} onChange={set("token")} /></label>}
        {mode !== "forgot" && <label>{mode === "reset" ? "New password" : "Password"}<input type="password" required minLength={mode === "login" ? 1 : 10} value={f.password} onChange={set("password")} />{mode !== "login" && <small className="muted">At least 10 characters.</small>}</label>}
        <button className="btn primary">{{ login: "Log in", register: "Create account", forgot: "Send reset token", reset: "Save new password" }[mode]}</button>
        <div className="login-links">
          {mode === "login" ? (<><button type="button" onClick={() => setMode("register")}>Create account</button><button type="button" onClick={() => setMode("forgot")}>Forgot password?</button></>)
            : <button type="button" onClick={() => setMode("login")}>Back to log in</button>}
        </div>
      </form>
    </div>
  );
}
