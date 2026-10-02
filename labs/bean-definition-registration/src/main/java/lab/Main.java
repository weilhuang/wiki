package lab;

import java.util.Arrays;
import org.springframework.context.support.ClassPathXmlApplicationContext;

public final class Main {
    public static void main(String[] args) {
        Catalog.resetCounters();
        try (var context = new ClassPathXmlApplicationContext()) {
            context.setAllowBeanDefinitionOverriding(false);
            context.setConfigLocation("classpath:/beans.xml");
            context.addBeanFactoryPostProcessor(factory -> {
                System.out.printf("registered: definitions=%d, aliases=%s, singleton=%s, constructed=%d%n",
                    factory.getBeanDefinitionCount(),
                    Arrays.toString(factory.getAliases("catalog")),
                    factory.containsSingleton("catalog"), Catalog.constructions);
            });
            context.refresh();
            System.out.printf("refreshed: singleton=%s, constructed=%d%n",
                context.getBeanFactory().containsSingleton("catalog"), Catalog.constructions);
            Catalog first = context.getBean("catalogAlias", Catalog.class);
            Catalog second = context.getBean("catalog", Catalog.class);
            System.out.printf("looked up: label=%s, same=%s, constructed=%d, initialized=%d%n",
                first.label(), first == second, Catalog.constructions, Catalog.initializations);
        }
        System.out.printf("closed: destroyed=%d%n", Catalog.destructions);
    }
}
