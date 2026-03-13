#include "fake_defs.h"
#include "fake_sync.h"
#include <linux/rcupdate.h>
#include <rcupdate.c>
#include "rcutree.c"
#include "fake_sched.h"

int cpu0 = 0;
int cpu1 = 1;

_Atomic int x;
_Atomic int y;
_Atomic int z;

int r_x;
int r_y;
int r_z;

void *thread_reader(void *arg)
{
    set_cpu(cpu1);
    fake_acquire_cpu(get_cpu());

    rcu_read_lock();
    /* extra delays make the failure schedule rarer */
    r_z = atomic_load_explicit(&z, memory_order_acquire);
    do_IRQ();
    cond_resched();
    r_y = atomic_load_explicit(&y, memory_order_acquire);
    do_IRQ();
    cond_resched();
    r_x = atomic_load_explicit(&x, memory_order_acquire);
#ifdef CHECK_BUG
    if (r_z == 1 && (r_x == 0 || r_y == 0)) {
        do_IRQ();
        cond_resched();
        int r_x2 = atomic_load_explicit(&x, memory_order_acquire);
        int r_y2 = atomic_load_explicit(&y, memory_order_acquire);
        int r_z2 = atomic_load_explicit(&z, memory_order_acquire);
        if (r_z2 == 1 && (r_x2 == 0 || r_y2 == 0)) {
            do_IRQ();
            cond_resched();
            int r_x3 = atomic_load_explicit(&x, memory_order_acquire);
            int r_y3 = atomic_load_explicit(&y, memory_order_acquire);
            int r_z3 = atomic_load_explicit(&z, memory_order_acquire);
            if (r_z3 == 1 && (r_x3 == 0 || r_y3 == 0))
                BUG_ON(1);
        }
    }
#endif
    rcu_read_unlock();

    fake_release_cpu(get_cpu());
    return NULL;
}

void *thread_update(void *arg)
{
    set_cpu(cpu0);
    fake_acquire_cpu(get_cpu());

#ifdef CHECK_BUG
    atomic_store_explicit(&z, 1, memory_order_release);
    do_IRQ();
    cond_resched();
    atomic_store_explicit(&y, 1, memory_order_release);
    do_IRQ();
    cond_resched();
    atomic_store_explicit(&x, 1, memory_order_release);
    do_IRQ();
    cond_resched();
#else
    atomic_store_explicit(&x, 1, memory_order_release);
    do_IRQ();
    cond_resched();
    atomic_store_explicit(&y, 1, memory_order_release);
    do_IRQ();
    cond_resched();
    atomic_store_explicit(&z, 1, memory_order_release);
#endif

    fake_release_cpu(get_cpu());
    return NULL;
}

int main(void)
{
    pthread_t tr, tu;

    rcu_scheduler_fully_active = 1;
    rcu_init();
    for (int i = 0; i < NR_CPUS; i++) {
        set_cpu(i);
        rcu_enter_nohz();
    }

    atomic_store(&x, 0);
    atomic_store(&y, 0);
    atomic_store(&z, 0);
    r_x = r_y = r_z = -1;

    if (pthread_create(&tu, NULL, thread_update, NULL))
        abort();
    (void)thread_reader(NULL);
    if (pthread_join(tu, NULL))
        abort();

#ifdef CHECK_BUG
    if (r_z == 1)
        BUG_ON(r_x != 1 || r_y != 1);
#endif

    return 0;
}
