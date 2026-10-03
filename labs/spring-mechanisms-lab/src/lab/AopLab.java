package lab;

import java.util.ArrayList;
import java.util.List;
import org.aopalliance.intercept.MethodInterceptor;
import org.springframework.aop.framework.Advised;
import org.springframework.aop.framework.ProxyFactory;
import org.springframework.aop.ProxyMethodInvocation;
import org.springframework.aop.framework.autoproxy.BeanNameAutoProxyCreator;
import org.springframework.aop.support.AopUtils;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;

public final class AopLab {
    public interface Gateway {
        String outer();
        String inner();
        Gateway self();
        void fail();
    }
    public static class Service implements Gateway {
        final List<String> events;
        final RuntimeException failure = new IllegalStateException("business-declined");
        int entries;
        static int finalEntries;
        Service(List<String> events) { this.events = events; }
        public String outer() {
            events.add("target.outer"); entries++;
            return inner() + privatePart();
        }
        public String inner() { events.add("target.inner"); entries++; return "ok"; }
        private String privatePart() { events.add("target.private"); entries++; return ":private"; }
        public Gateway self() { events.add("target.self"); entries++; return this; }
        public void fail() { events.add("target.fail"); entries++; throw failure; }
        public final Object finalIdentity() { finalEntries++; return this; }
    }
    public interface FinalApi { int finalCall(); }
    public static final class FinalService implements FinalApi {
        int entries;
        public final int finalCall() { return ++entries; }
    }
    static void require(boolean ok, String label) {
        if (!ok) throw new AssertionError(label);
    }
    static MethodInterceptor trace(String name, List<String> events, Service target) {
        return invocation -> {
            require(invocation.getThis() == target, "advice receiver is target");
            require(((ProxyMethodInvocation) invocation).getProxy() != target, "proxy differs from target");
            String method = invocation.getMethod().getName();
            events.add(name + ">" + method);
            try { return invocation.proceed(); }
            finally { events.add("<" + name + ":" + method); }
        };
    }
    static void contextDispatch(boolean classProxy, String mutation) throws Exception {
        List<String> events = new ArrayList<>();
        Service target = new Service(events);
        try (var context = new AnnotationConfigApplicationContext()) {
            context.registerBean("autoProxyCreator", BeanNameAutoProxyCreator.class, () -> {
                var creator = new BeanNameAutoProxyCreator();
                creator.setBeanNames("gateway");
                creator.setProxyTargetClass(classProxy);
                creator.setInterceptorNames("first", "second");
                return creator;
            });
            context.registerBean("first", MethodInterceptor.class, () -> trace("A", events, target));
            context.registerBean("second", MethodInterceptor.class, () -> trace("B", events, target));
            context.registerBean("gateway", Service.class, () -> target);
            context.refresh();
            Gateway proxy = context.getBean("gateway", Gateway.class);
            require(proxy != target && ((Advised) proxy).getTargetSource().getTarget() == target, "target identity");
            require(context.getBean("gateway") == proxy, "singleton proxy identity");
            require(context.getBeansOfType(Gateway.class).size() == 1, "one gateway bean");
            require(classProxy ? AopUtils.isCglibProxy(proxy) : AopUtils.isJdkDynamicProxy(proxy), "proxy strategy");
            Gateway receiver = mutation.equals("bypass-proxy") ? target : proxy;
            String result = receiver.outer();
            require(result.equals("ok:private") && target.entries == 3, "outer business result and entries");
            require(events.equals(List.of("A>outer", "B>outer", "target.outer", "target.inner", "target.private", "<B:outer", "<A:outer")), "outer advice order and self invocation boundary");
            events.clear();
            int previous = target.entries;
            require(proxy.inner().equals("ok") && target.entries == previous + 1, "external inner enters once");
            require(events.equals(List.of("A>inner", "B>inner", "target.inner", "<B:inner", "<A:inner")), "external inner advice order");
            events.clear();
            require(proxy.self() == proxy && target.entries == previous + 2, "Spring self return is proxy");
            require(events.equals(List.of("A>self", "B>self", "target.self", "<B:self", "<A:self")), "self return advised once");
            events.clear();
            RuntimeException caught = null;
            try { proxy.fail(); } catch (RuntimeException ex) { caught = ex; }
            require(caught == target.failure && target.entries == previous + 3, "business exception identity and entry");
            require(events.equals(List.of("A>fail", "B>fail", "target.fail", "<B:fail", "<A:fail")), "exception unwinds advice");
            events.clear();
            target.inner();
            require(events.equals(List.of("target.inner")) && target.entries == previous + 4, "raw target bypass");
            if (classProxy) {
                events.clear(); Service.finalEntries = 0;
                Object actual = ((Service) proxy).finalIdentity();
                require(actual == proxy && actual != target && Service.finalEntries == 1 && events.isEmpty(), "final executes on proxy without advice");
            } else {
                require(!(proxy instanceof Service), "JDK proxy is not Service");
                try { Service ignored = (Service) proxy; throw new AssertionError("cast must fail"); }
                catch (ClassCastException expected) { require(expected.getMessage() != null, "cast reason recorded"); }
            }
            System.out.println("PASS context " + (classProxy ? "CGLIB" : "JDK") + " targetEntries=" + target.entries + " businessException=original; context will close");
        }
    }
    static void finalBoundary() {
        FinalService target = new FinalService();
        List<String> events = new ArrayList<>();
        var factory = new ProxyFactory(target);
        factory.addAdvice((MethodInterceptor) invocation -> {
            events.add("before"); Object value = invocation.proceed(); events.add("after"); return value;
        });
        FinalApi proxy = (FinalApi) factory.getProxy();
        require(AopUtils.isJdkDynamicProxy(proxy) && proxy.finalCall() == 1 && target.entries == 1, "final method on final target via interface");
        require(events.equals(List.of("before", "after")), "JDK advises final target method");
        factory.setProxyTargetClass(true);
        Throwable failure = null;
        try { factory.getProxy(); } catch (RuntimeException ex) { failure = ex; }
        require(failure instanceof org.springframework.aop.framework.AopConfigException, "final class outer error");
        Throwable root = failure; while (root.getCause() != null) root = root.getCause();
        require(root instanceof IllegalArgumentException && root.getMessage().contains("Cannot subclass final class"), "final class cause");
        System.out.println("EXPECTED final-class rejection"); failure.printStackTrace(System.out);
    }
    static void shortCircuit(String mutation) {
        List<String> events = new ArrayList<>(); Service target = new Service(events);
        var factory = new ProxyFactory(target);
        factory.addAdvice((MethodInterceptor) invocation -> {
            events.add("cache.hit");
            if (mutation.equals("proceed-on-cache-hit")) invocation.proceed();
            return "cached";
        });
        Gateway proxy = (Gateway) factory.getProxy(); String result = proxy.inner();
        System.out.println("OBSERVE cache result=" + result + " targetEntries=" + target.entries + " events=" + events);
        require(result.equals("cached") && target.entries == 0 && events.equals(List.of("cache.hit")), "cache hit must skip business");
        System.out.println("PASS short circuit result=cached targetEntries=0");
    }
    public static void main(String[] args) throws Exception {
        String mutation = args.length == 0 ? "none" : args[0];
        require(List.of("none", "bypass-proxy", "proceed-on-cache-hit").contains(mutation), "known mutation");
        contextDispatch(false, mutation); contextDispatch(true, mutation);
        finalBoundary(); shortCircuit(mutation);
        System.out.println("PASS AOP complete");
    }
}
