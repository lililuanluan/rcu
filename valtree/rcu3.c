#include "fake_defs.h"
#include "fake_sync.h"
#include <stdint.h>
#include <stdatomic.h>
#include <linux/rcupdate.h>
#include <rcupdate.c>
#include "rcutree.c"
#include "fake_sched.h"

#define N 15

_Atomic int value;
_Atomic int flag;

void *thread_writer(void *arg)
{
    set_cpu((intptr_t)arg);
    fake_acquire_cpu(get_cpu());

    for (int i = 0; i < N; i++) {
        atomic_store_explicit(&value, 0, memory_order_relaxed);
        atomic_store_explicit(&flag, 0, memory_order_relaxed);
        do_IRQ();
        cond_resched();

#ifdef CHECK_BUG
        atomic_store_explicit(&flag, 1, memory_order_release);
        do_IRQ();
        cond_resched();
        atomic_store_explicit(&value, 1, memory_order_relaxed);
#else
        atomic_store_explicit(&value, 1, memory_order_relaxed);
        do_IRQ();
        cond_resched();
        atomic_store_explicit(&flag, 1, memory_order_release);
#endif

        do_IRQ();
        cond_resched();
    }

    fake_release_cpu(get_cpu());
    return NULL;
}

void *thread_reader(void *arg)
{
    set_cpu((intptr_t)arg);
    fake_acquire_cpu(get_cpu());

    rcu_read_lock();
    for (int i = 0; i < N; i++) {
        int f = atomic_load_explicit(&flag, memory_order_acquire);
        do_IRQ();
        cond_resched();
        int v = atomic_load_explicit(&value, memory_order_relaxed);

#ifdef CHECK_BUG
        if (f == 1 && v == 0)
            BUG_ON(1);
#endif

        do_IRQ();
        cond_resched();
    }
    rcu_read_unlock();

    fake_release_cpu(get_cpu());
    return NULL;
}

int main(void)
{
    pthread_t tw, tr;

    rcu_scheduler_fully_active = 1;
    rcu_init();
    for (int i = 0; i < NR_CPUS; i++) {
        set_cpu(i);
        rcu_enter_nohz();
    }

    atomic_store(&value, 0);
    atomic_store(&flag, 0);

    if (pthread_create(&tw, NULL, thread_writer, (void*)0))
        abort();
    if (pthread_create(&tr, NULL, thread_reader, (void*)1))
        abort();

    if (pthread_join(tw, NULL))
        abort();
    if (pthread_join(tr, NULL))
        abort();

    return 0;
}
