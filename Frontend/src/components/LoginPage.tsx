import React, { useState } from "react";
import { supabase } from "../lib/supabase";

export interface LoginPageProps {
  isVisible: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({
  isVisible,
  onClose,
  onSuccess,
}) => {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const handleEmailAuth = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    setLoading(true);

    try {
      if (isSignUp) {
        if (password !== confirmPassword) {
          setError("Passwords do not match");
          setLoading(false);
          return;
        }

        const { error } = await supabase.auth.signUp({
          email,
          password,
        });

        if (error) throw error;
        setMessage("Check your email for the confirmation link!");
      } else {
        const { error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (error) throw error;
        onSuccess();
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
      });
      if (error) throw error;
    } catch (err: any) {
      setError(err.message);
      setLoading(false);
    }
  };

  const resetForm = () => {
    setEmail("");
    setPassword("");
    setConfirmPassword("");
    setError(null);
    setMessage(null);
  };

  const toggleMode = () => {
    setIsSignUp(!isSignUp);
    resetForm();
  };

  return (
    <div
      className={`fixed inset-0 z-[60] flex items-center justify-center
        transform transition-all duration-300 ease-in-out
        ${isVisible ? "opacity-100" : "opacity-0 pointer-events-none"}
      `}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-rich-black/80" onClick={onClose} />

      {/* Modal */}
      <div
        className={`relative w-full max-w-4xl mx-4 bg-dark-green overflow-hidden shadow-2xl
          transform transition-all duration-300 ease-in-out
          ${isVisible ? "scale-100 translate-y-0" : "scale-95 translate-y-4"}
        `}
      >
        <div className="flex flex-col md:flex-row min-h-[500px]">
          {/* Left Side - Map Illustration */}
          <div className="hidden md:flex md:w-1/2 bg-gradient-to-br from-bangladesh-green via-forest to-pine p-8 flex-col justify-between relative overflow-hidden">
            {/* Decorative Map Elements */}
            <div className="absolute inset-0 opacity-20">
              {/* Grid lines */}
              <div
                className="absolute inset-0"
                style={{
                  backgroundImage: `
                  linear-gradient(to right, rgba(255,255,255,0.1) 1px, transparent 1px),
                  linear-gradient(to bottom, rgba(255,255,255,0.1) 1px, transparent 1px)
                `,
                  backgroundSize: "40px 40px",
                }}
              />

              {/* Circular markers */}
              <div className="absolute top-1/4 left-1/4 w-4 h-4 bg-mountain-meadow animate-pulse" />
              <div
                className="absolute top-1/3 right-1/3 w-3 h-3 bg-caribbean-green animate-pulse"
                style={{ animationDelay: "0.5s" }}
              />
              <div
                className="absolute bottom-1/3 left-1/2 w-5 h-5 bg-mint animate-pulse"
                style={{ animationDelay: "1s" }}
              />
              <div
                className="absolute top-2/3 left-1/4 w-3 h-3 bg-mountain-meadow animate-pulse"
                style={{ animationDelay: "1.5s" }}
              />
              <div
                className="absolute bottom-1/4 right-1/4 w-4 h-4 bg-caribbean-green animate-pulse"
                style={{ animationDelay: "0.3s" }}
              />

              {/* Connection lines */}
              <svg
                className="absolute inset-0 w-full h-full"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
              >
                <path
                  d="M25 25 L35 33 L50 35 L75 65"
                  stroke="rgba(44, 194, 149, 0.3)"
                  strokeWidth="0.3"
                  fill="none"
                />
                <path
                  d="M25 65 L50 35 L75 25"
                  stroke="rgba(0, 123, 129, 0.3)"
                  strokeWidth="0.3"
                  fill="none"
                />
              </svg>
            </div>

            {/* Content */}
            <div className="relative z-10">
              <h1 className="text-3xl font-bold text-white mb-2">REACH</h1>
              <p className="text-stone text-sm">
                Real-time Emergency Alert & Communication Hub
              </p>
            </div>

            <div className="relative z-10">
              {/* Map Icon */}
              <div className="mb-6">
                <svg
                  className="w-32 h-32 text-mountain-meadow opacity-80"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="0.5"
                    d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l5.447 2.724A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7"
                  />
                </svg>
              </div>

              <h2 className="text-2xl font-semibold text-white mb-3">
                Stay Informed.
                <br />
                Stay Safe.
              </h2>
              <p className="text-stone text-sm leading-relaxed">
                Get real-time disaster alerts and emergency notifications for
                your area. Create an account to customize your alerts and
                receive notifications.
              </p>
            </div>
          </div>

          {/* Right Side - Login Form */}
          <div className="w-full md:w-1/2 p-8 flex flex-col justify-center bg-rich-black">
            {/* Close button */}
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-2 hover:bg-white/10 transition-colors text-gray-400 hover:text-white"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>

            <div className="max-w-sm mx-auto w-full">
              <h2 className="text-2xl font-bold text-white mb-2">
                {isSignUp ? "Create Account" : "Welcome Back"}
              </h2>
              <p className="text-stone text-sm mb-8">
                {isSignUp
                  ? "Sign up to get personalized alerts and notifications"
                  : "Sign in to access your personalized settings"}
              </p>

              {/* Error/Message Display */}
              <div
                className="overflow-hidden transition-all duration-300 ease-in-out"
                style={{
                  maxHeight: error ? "80px" : "0",
                  opacity: error ? 1 : 0,
                  marginBottom: error ? "16px" : "0",
                }}
              >
                <div className="p-3 bg-red-900/50 border border-red-700 rounded-md">
                  <p className="text-sm text-red-200">{error}</p>
                </div>
              </div>
              <div
                className="overflow-hidden transition-all duration-300 ease-in-out"
                style={{
                  maxHeight: message ? "80px" : "0",
                  opacity: message ? 1 : 0,
                  marginBottom: message ? "16px" : "0",
                }}
              >
                <div className="p-3 bg-green-900/50 border border-green-700 rounded-md">
                  <p className="text-sm text-green-200">{message}</p>
                </div>
              </div>

              {/* Email/Password Form */}
              <form onSubmit={handleEmailAuth} className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="filter-input w-full px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none"
                    placeholder="you@example.com"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="filter-input w-full px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none"
                    placeholder="••••••••"
                    required
                    minLength={6}
                  />
                </div>

                <div
                  className="overflow-hidden transition-all duration-300 ease-in-out"
                  style={{
                    maxHeight: isSignUp ? "80px" : "0",
                    opacity: isSignUp ? 1 : 0,
                  }}
                >
                  <label className="block text-sm text-gray-400 mb-1.5">
                    Confirm Password
                  </label>
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="filter-input w-full px-4 py-2.5 text-white placeholder-gray-500 focus:outline-none"
                    placeholder="••••••••"
                    required={isSignUp}
                    minLength={6}
                    tabIndex={isSignUp ? 0 : -1}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-3 bg-bangladesh-green rounded-lg hover:bg-mountain-meadow text-white hover:text-dark-green font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                      <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
                      {isSignUp ? "Creating Account..." : "Signing In..."}
                    </span>
                  ) : isSignUp ? (
                    "Create Account"
                  ) : (
                    "Sign In"
                  )}
                </button>
              </form>

              {/* Divider */}
              <div className="relative mb-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-stone/30"></div>
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="px-2 bg-rich-black text-stone">
                    or continue with
                  </span>
                </div>
              </div>

              {/* Google Login */}
              <button
                onClick={handleGoogleLogin}
                disabled={loading}
                className="w-full flex items-center justify-center gap-3 py-3 rounded-lg bg-white text-rich-black font-semibold hover:bg-gray-100 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                    fill="#4285F4"
                  />
                  <path
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                    fill="#34A853"
                  />
                  <path
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                    fill="#FBBC05"
                  />
                  <path
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                    fill="#EA4335"
                  />
                </svg>
                <span style={{ fontFamily: "system-ui" }}>Google</span>
              </button>

              {/* Toggle Sign Up / Sign In */}
              <p className="mt-6 text-center text-sm text-stone">
                {isSignUp
                  ? "Already have an account?"
                  : "Don't have an account?"}{" "}
                <button
                  onClick={toggleMode}
                  className="text-bangladesh-green hover:text-mountain-meadow font-medium transition-colors"
                >
                  {isSignUp ? "Sign In" : "Sign Up"}
                </button>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
