package lab;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.AutoConfigurations;
import org.springframework.boot.autoconfigure.EnableAutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.autoconfigure.condition.ConditionEvaluationReport;
import org.springframework.boot.test.context.FilteredClassLoader;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

public final class BootLab {
    interface ReceiptStore { String origin(); }
    static final class AutoStore implements ReceiptStore {
        static int creations;
        AutoStore() { creations++; }
        public String origin() { return "auto"; }
    }
    static final class UserStore implements ReceiptStore {
        public String origin() { return "user"; }
    }
    @AutoConfiguration
    @ConditionalOnClass(name = "lab.OptionalClient")
    @ConditionalOnProperty(prefix = "receipt", name = "enabled", havingValue = "true", matchIfMissing = true)
    public static class ReceiptAuto {
        @Bean
        @ConditionalOnMissingBean(ReceiptStore.class)
        AutoStore receiptStore() { return new AutoStore(); }
    }
    @AutoConfiguration
    @ConditionalOnClass(name = "lab.OptionalClient")
    @ConditionalOnProperty(prefix = "receipt", name = "enabled", havingValue = "true", matchIfMissing = true)
    public static class BadReceiptAuto {
        @Bean AutoStore extraReceiptStore() { return new AutoStore(); }
    }
    @Configuration(proxyBeanMethods = false)
    @EnableAutoConfiguration
    public static class ImportsEntry {}
    static final List<String> CREATION_ORDER = new ArrayList<>();
    record Token(String value) {}
    record Consumer(Token token) {}
    @AutoConfiguration(before = TokenAuto.class)
    public static class ConsumerAuto {
        @Bean Consumer consumer(Token token) { CREATION_ORDER.add("consumer"); return new Consumer(token); }
    }
    @AutoConfiguration
    public static class TokenAuto {
        @Bean Token token() { CREATION_ORDER.add("token"); return new Token("ready"); }
    }
    @AutoConfiguration(before = TokenAuto.class)
    @ConditionalOnBean(Token.class)
    public static class TooEarlyAuto {
        @Bean String earlyWitness() { return "saw-token"; }
    }
    @AutoConfiguration(after = TokenAuto.class)
    @ConditionalOnBean(Token.class)
    public static class AfterTokenAuto {
        @Bean String lateWitness() { return "saw-token"; }
    }
    static void require(boolean ok, String label) { if (!ok) throw new AssertionError(label); }
    static void report(org.springframework.boot.test.context.assertj.AssertableApplicationContext context,
                       String sourceSuffix, String condition, boolean expectedMatch, String reasonFragment) {
        var report = ConditionEvaluationReport.get(context.getBeanFactory());
        var outcomes = report.getConditionAndOutcomesBySource().entrySet().stream()
                .filter(e -> e.getKey().endsWith(sourceSuffix)).findFirst().orElseThrow().getValue();
        boolean found = false;
        for (var item : outcomes) {
            if (item.getCondition().getClass().getSimpleName().equals(condition)) {
                String message = item.getOutcome().getMessage();
                require(item.getOutcome().isMatch() == expectedMatch && message != null && message.contains(reasonFragment), "condition outcome and cause: " + sourceSuffix + " / " + condition);
                System.out.println("REPORT " + sourceSuffix + " " + condition + " match=" + expectedMatch + " " + message);
                found = true;
            }
        }
        require(found, "condition report exists: " + condition);
    }
    static void oneAuto(org.springframework.boot.test.context.assertj.AssertableApplicationContext context) {
        require(context.getStartupFailure() == null, "context started");
        Map<String, ReceiptStore> beans = context.getBeansOfType(ReceiptStore.class);
        require(beans.size() == 1 && beans.containsKey("receiptStore"), "one auto store");
        ReceiptStore store = beans.get("receiptStore");
        require(store.getClass() == AutoStore.class && store.origin().equals("auto") && context.getBean(ReceiptStore.class) == store, "auto type and singleton identity");
    }
    public static void main(String[] args) throws Exception {
        String mutation = args.length == 0 ? "none" : args[0];
        require(List.of("none", "remove-backoff").contains(mutation), "known mutation");
        var runner = new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(ReceiptAuto.class));
        int initial = AutoStore.creations;
        runner.run(context -> {
            oneAuto(context);
            report(context, "BootLab$ReceiptAuto", "OnClassCondition", true, "lab.OptionalClient");
            report(context, "BootLab$ReceiptAuto#receiptStore", "OnBeanCondition", true, "did not find any beans");
        });
        require(AutoStore.creations == initial + 1, "auto constructor once");
        runner.withPropertyValues("receipt.enabled=false").run(context -> {
            require(context.getStartupFailure() == null && context.getBeansOfType(ReceiptStore.class).isEmpty(), "property disables store");
            report(context, "BootLab$ReceiptAuto", "OnPropertyCondition", false, "different value");
        });
        try (var loader = new FilteredClassLoader(OptionalClient.class)) {
            runner.withClassLoader(loader).run(context -> {
                require(context.getStartupFailure() == null && context.getBeansOfType(ReceiptStore.class).isEmpty(), "missing class disables store");
                report(context, "BootLab$ReceiptAuto", "OnClassCondition", false, "lab.OptionalClient");
            });
        }
        UserStore supplied = new UserStore();
        var userRunner = new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(
                mutation.equals("remove-backoff") ? BadReceiptAuto.class : ReceiptAuto.class));
        int beforeUser = AutoStore.creations;
        userRunner.withBean("userReceiptStore", ReceiptStore.class, () -> supplied).run(context -> {
            require(context.getStartupFailure() == null, "user context started");
            Map<String, ReceiptStore> beans = context.getBeansOfType(ReceiptStore.class);
            require(beans.size() == 1 && beans.get("userReceiptStore") == supplied, "user bean identity and single implementation");
            require(context.getBean(ReceiptStore.class) == supplied && supplied.origin().equals("user"), "user implementation selected");
            report(context, "BootLab$ReceiptAuto#receiptStore", "OnBeanCondition", false, "userReceiptStore");
        });
        require(AutoStore.creations == beforeUser, "backoff avoids auto constructor");
        CREATION_ORDER.clear();
        new ApplicationContextRunner().withConfiguration(AutoConfigurations.of(TokenAuto.class, ConsumerAuto.class, TooEarlyAuto.class, AfterTokenAuto.class)).run(context -> {
            require(context.getStartupFailure() == null, "ordered context started");
            require(context.getBean(Consumer.class).token() == context.getBean(Token.class), "consumer token identity");
            require(CREATION_ORDER.equals(List.of("token", "consumer")), "dependency determines construction order");
            require(!context.containsBean("earlyWitness") && context.getBean("lateWitness").equals("saw-token"), "condition sees definitions processed so far");
            report(context, "BootLab$TooEarlyAuto", "OnBeanCondition", false, "did not find any beans");
            report(context, "BootLab$AfterTokenAuto", "OnBeanCondition", true, "token");
        });
        new ApplicationContextRunner().withUserConfiguration(ImportsEntry.class).run(context -> {
            oneAuto(context);
            require(context.getBeanFactory().containsBeanDefinition(ReceiptAuto.class.getName()), "imports candidate registered through EnableAutoConfiguration");
        });
        System.out.println("PASS BOOT complete; all runner contexts closed; construction=" + CREATION_ORDER);
    }
}
