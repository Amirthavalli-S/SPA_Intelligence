import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthGate } from "./auth/AuthGate";
import { homeRouteFor, kindOf } from "./auth/roles";
import { useAuth } from "./auth/useAuth";
import { DisclaimerBar } from "./components/Disclaimer";
import { TopBar } from "./components/TopBar";
import { RouteFade, TransitionProvider } from "./motion/Transition";
import { loadDevtools } from "./motion/registry";

const Landing = lazy(() => import("./pages/Landing"));
const RoleSwitch = lazy(() => import("./pages/RoleSwitch"));
const Reset = lazy(() => import("./pages/Reset"));
const NotFound = lazy(() => import("./pages/NotFound"));
const Login = lazy(() => import("./pages/Login"));
const Enterprise = lazy(() => import("./pages/Enterprise"));

void loadDevtools(); // dev-only (?devtools=1); compiled away in production builds

/** Staff in a department never see the general front page: Home for them IS their department's home. */
function HomeGate({ children }: { children: ReactNode }) {
  const me = useAuth();
  const kind = kindOf(me.data);
  if (kind === "staff" && me.data?.department) return <Navigate to={homeRouteFor(kind, me.data.department)} replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <TransitionProvider>
      <TopBar />
      <main>
        <RouteFade>
          <Suspense fallback={<div style={{ minHeight: "100svh" }} aria-busy="true" />}>
            <Routes>
              <Route
                path="/"
                element={
                  <AuthGate>
                    <HomeGate>
                      <Landing />
                    </HomeGate>
                  </AuthGate>
                }
              />
              <Route
                path="/enterprise"
                element={
                  <AuthGate>
                    <HomeGate>
                      <Enterprise />
                    </HomeGate>
                  </AuthGate>
                }
              />
              <Route path="/login" element={<Login />} />
              <Route path="/reset" element={<Reset />} />
              <Route
                path="/app/*"
                element={
                  <AuthGate>
                    <RoleSwitch />
                  </AuthGate>
                }
              />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </RouteFade>
      </main>
      <DisclaimerBar />
    </TransitionProvider>
  );
}
