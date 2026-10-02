package lab;

import org.springframework.beans.NotWritablePropertyException;
import org.springframework.beans.factory.BeanCreationException;
import org.springframework.beans.factory.BeanDefinitionStoreException;
import org.springframework.beans.factory.NoSuchBeanDefinitionException;
import org.springframework.beans.factory.parsing.BeanDefinitionParsingException;
import org.springframework.beans.factory.support.BeanDefinitionOverrideException;
import org.springframework.beans.factory.support.DefaultListableBeanFactory;
import org.springframework.beans.factory.xml.XmlBeanDefinitionReader;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.context.support.ClassPathXmlApplicationContext;

/** Independent of Java's optional -ea switch and of console output matching. */
public final class BeanDefinitionLabTests {
    private static int passed;
    private static int checks;

    public static void main(String[] args) {
        run("raw reader registers even an eager definition without creating it", () -> {
            var factory = factory(false);
            int added = new XmlBeanDefinitionReader(factory).loadBeanDefinitions("classpath:/eager.xml");
            eq(1, added, "added definitions");
            eq(1, factory.getBeanDefinitionCount(), "definition count");
            eq(false, factory.getBeanDefinition("catalog").isLazyInit(), "explicitly eager fixture");
            eq(false, factory.containsSingleton("catalog"), "no singleton after read");
            eq(0, Catalog.constructions, "no constructor at registration");
            eq("alpha", factory.getBean("catalog", Catalog.class).label(), "factory creates on getBean");
            eq(1, Catalog.initializations, "init executed");
            factory.destroySingletons();
            eq(1, Catalog.destructions, "raw factory owner requests destruction");
        });
        run("lazy context defers creation and aliases resolve to one identity", () -> {
            boolean[] observed = {false};
            try (var context = context("beans.xml")) {
                context.addBeanFactoryPostProcessor(factory -> {
                    observed[0] = true;
                    eq(1, factory.getBeanDefinitionCount(), "one definition, alias not counted");
                    eq(false, factory.containsSingleton("catalog"), "definition phase");
                    eq(0, Catalog.constructions, "no construction in callback");
                });
                context.refresh();
                eq(true, observed[0], "postprocessor ran");
                eq(false, context.getBeanFactory().containsSingleton("catalog"), "lazy after refresh");
                eq(true, context.containsBean("catalogAlias"), "alias is lookup name");
                eq(false, context.containsBeanDefinition("catalogAlias"), "alias is not definition key");
                expect(NoSuchBeanDefinitionException.class,
                    () -> context.getBeanFactory().getBeanDefinition("catalogAlias"));
                Object alias = context.getBean("catalogAlias");
                same(alias, context.getBean("catalog"), "same singleton");
                eq(1, Catalog.constructions, "one construction");
                eq(1, Catalog.initializations, "one init");
            }
            eq(1, Catalog.destructions, "one managed destruction");
        });
        run("eager context creates before refresh returns", () -> {
            try (var context = context("eager.xml")) {
                context.refresh();
                eq(true, context.getBeanFactory().containsSingleton("catalog"), "eager singleton");
                eq(1, Catalog.constructions, "created during refresh");
                eq(1, Catalog.initializations, "initialized during refresh");
            }
            eq(1, Catalog.destructions, "context destruction");
        });
        run("an eager dependency can force a lazy bean to be created", () -> {
            try (var context = context("eager-consumer.xml")) {
                context.refresh();
                eq(1, Catalog.constructions, "lazy required by eager consumer");
                same(context.getBean("catalog"), context.getBean(Consumer.class).catalog, "injected instance");
            }
        });
        run("override false rejects second resource and preserves first definition", () -> {
            var factory = factory(false);
            var reader = new XmlBeanDefinitionReader(factory);
            reader.loadBeanDefinitions("classpath:/eager.xml");
            expectCause(BeanDefinitionStoreException.class, BeanDefinitionOverrideException.class,
                () -> reader.loadBeanDefinitions("classpath:/beta.xml"));
            eq(1, factory.getBeanDefinitionCount(), "first definition still registered");
            eq(0, Catalog.constructions, "failure did not instantiate");
            eq("alpha", factory.getBean("catalog", Catalog.class).label(), "original definition preserved");
            factory.destroySingletons();
        });
        run("override true replaces a definition with zero net count increase", () -> {
            var factory = factory(true);
            var reader = new XmlBeanDefinitionReader(factory);
            eq(1, reader.loadBeanDefinitions("classpath:/eager.xml"), "first delta");
            eq(0, reader.loadBeanDefinitions("classpath:/beta.xml"), "replacement delta");
            eq(1, factory.getBeanDefinitionCount(), "one definition");
            eq(0, Catalog.constructions, "no instance yet");
            eq("beta", factory.getBean("catalog", Catalog.class).label(), "replacement used");
            factory.destroySingletons();
        });
        run("duplicate names in one beans element fail even when override is true", () -> {
            var factory = factory(true);
            expect(BeanDefinitionParsingException.class,
                () -> new XmlBeanDefinitionReader(factory).loadBeanDefinitions("classpath:/duplicate-in-one.xml"));
            eq(1, factory.getBeanDefinitionCount(), "earlier registration is not rolled back");
            eq(0, Catalog.constructions, "parse error before instantiation");
        });
        run("malformed XML fails before any definition is registered", () -> {
            var factory = factory(false);
            expect(BeanDefinitionStoreException.class,
                () -> new XmlBeanDefinitionReader(factory).loadBeanDefinitions("classpath:/malformed.xml"));
            eq(0, factory.getBeanDefinitionCount(), "DOM load failed before registration");
        });
        run("missing classpath resource fails while opening the resource", () -> {
            var factory = factory(false);
            expectCause(BeanDefinitionStoreException.class, java.io.FileNotFoundException.class,
                () -> new XmlBeanDefinitionReader(factory).loadBeanDefinitions("classpath:/not-present.xml"));
            eq(0, factory.getBeanDefinitionCount(), "nothing registered");
        });
        run("unknown property registers but fails during population", () -> {
            var factory = factory(false);
            eq(1, new XmlBeanDefinitionReader(factory).loadBeanDefinitions("classpath:/bad-property.xml"), "load succeeds");
            eq(0, Catalog.constructions, "not yet constructed");
            expectCause(BeanCreationException.class, NotWritablePropertyException.class,
                () -> factory.getBean("catalog"));
            eq(1, Catalog.constructions, "constructor already ran");
            eq(false, factory.containsSingleton("catalog"), "failed object not published");
        });
        run("unresolved bean reference fails when a consumer is created", () -> {
            var factory = factory(false);
            eq(1, new XmlBeanDefinitionReader(factory).loadBeanDefinitions("classpath:/missing-reference.xml"), "reference is metadata");
            expectCause(BeanCreationException.class, NoSuchBeanDefinitionException.class,
                () -> factory.getBean("consumer"));
            eq(false, factory.containsSingleton("consumer"), "failed consumer not published");
        });
        run("factory postprocessor changes definition before ordinary creation", () -> {
            try (var context = context("beans.xml")) {
                context.addBeanFactoryPostProcessor(factory -> {
                    eq(0, Catalog.constructions, "still only definition");
                    factory.getBeanDefinition("catalog").getPropertyValues().add("label", "rewritten");
                });
                context.refresh();
                eq("rewritten", context.getBean("catalog", Catalog.class).label(), "metadata change affects later object");
            }
        });
        run("annotation entry produces bean-method definition during refresh", () -> {
            try (var context = new AnnotationConfigApplicationContext()) {
                context.setAllowBeanDefinitionOverriding(false);
                context.register(AnnotationInput.class);
                eq(false, context.containsBeanDefinition("annotatedCatalog"), "bean method not parsed by register alone");
                context.refresh();
                eq(true, context.containsBeanDefinition("annotatedCatalog"), "configuration processor registered method");
                eq("annotatedCatalog", context.getBeanFactory().getBeanDefinition("annotatedCatalog").getFactoryMethodName(), "factory method metadata");
                eq(0, Catalog.constructions, "lazy annotated product");
                eq("annotation", context.getBean("annotatedCatalog", Catalog.class).label(), "method product");
            }
        });
        System.out.printf("PASS: %d scenarios, %d assertions%n", passed, checks);
    }

    static DefaultListableBeanFactory factory(boolean override) {
        var factory = new DefaultListableBeanFactory();
        factory.setAllowBeanDefinitionOverriding(override);
        return factory;
    }
    static ClassPathXmlApplicationContext context(String resource) {
        var context = new ClassPathXmlApplicationContext();
        context.setAllowBeanDefinitionOverriding(false);
        context.setConfigLocation("classpath:/" + resource);
        return context;
    }
    static void run(String name, Runnable test) {
        Catalog.resetCounters();
        test.run();
        passed++;
        System.out.println("PASS " + passed + ": " + name);
    }
    static void eq(Object expected, Object actual, String message) {
        checks++;
        if (!java.util.Objects.equals(expected, actual))
            throw new AssertionError(message + ": expected=" + expected + ", actual=" + actual);
    }
    static void same(Object expected, Object actual, String message) {
        checks++;
        if (expected != actual) throw new AssertionError(message);
    }
    static Throwable expect(Class<? extends Throwable> type, Runnable action) {
        checks++;
        try { action.run(); }
        catch (Throwable failure) {
            if (type.isInstance(failure)) return failure;
            throw new AssertionError("expected " + type.getName() + " but got " + failure, failure);
        }
        throw new AssertionError("expected " + type.getName() + " but no exception was thrown");
    }
    static void expectCause(Class<? extends Throwable> outer, Class<? extends Throwable> cause, Runnable action) {
        Throwable failure = expect(outer, action);
        checks++;
        for (Throwable current = failure; current != null; current = current.getCause())
            if (cause.isInstance(current)) return;
        throw new AssertionError("missing cause " + cause.getName(), failure);
    }
    public static final class Consumer {
        Catalog catalog;
        public void setCatalog(Catalog catalog) { this.catalog = catalog; }
    }
    @Configuration(proxyBeanMethods = false)
    public static class AnnotationInput {
        @Bean @Lazy
        public Catalog annotatedCatalog() {
            var catalog = new Catalog();
            catalog.setLabel("annotation");
            return catalog;
        }
    }
}
