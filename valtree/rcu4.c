#include "fake_defs.h"
#include "fake_sync.h"
#include <stdint.h>
#include <stdatomic.h>
#include <linux/rcupdate.h>
#include <rcupdate.c>
#include "rcutree.c"
#include "fake_sched.h"

/*
 * Slot publication pattern (not value+flag).
 *
 * Writer cycles through a small ring of slots and publishes a generation
 * number. The correct order is: write slot value, then publish idx/gen.
 * The buggy order publishes idx/gen before the slot update, allowing the
 * reader to observe a stable gen/idx pair but a stale slot value.
 */

#define N 20
#define SLOTS 4

_Atomic int gen;
_Atomic int idx;
_Atomic int slots[SLOTS];

void *thread_writer(void *arg)
{
    set_cpu((intptr_t)arg);
    fake_acquire_cpu(get_cpu());

    for (int i = 0; i < N; i++) {
        int g = atomic_load_explicit(&gen, memory_order_relaxed) + 1;
        int s = g & (SLOTS - 1);

        atomic_store_explicit(&slots[s], 0, memory_order_relaxed);
        do_IRQ();
        cond_resched();

#ifdef CHECK_BUG
        /* Bug: publish idx/gen before slot value is ready. */
        atomic_store_explicit(&idx, s, memory_order_release);
        atomic_store_explicit(&gen, g, memory_order_release);
        do_IRQ();
        cond_resched();
        atomic_store_explicit(&slots[s], g, memory_order_release);
#else
        atomic_store_explicit(&slots[s], g, memory_order_release);
        do_IRQ();
        cond_resched();
        atomic_store_explicit(&idx, s, memory_order_release);
        atomic_store_explicit(&gen, g, memory_order_release);
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
    for (int i = 0; i < N * 2; i++) {
        int g1 = atomic_load_explicit(&gen, memory_order_acquire);
        int s1 = atomic_load_explicit(&idx, memory_order_acquire);
        do_IRQ();
        cond_resched();
        int v = atomic_load_explicit(&slots[s1], memory_order_acquire);
        do_IRQ();
        cond_resched();
        int g2 = atomic_load_explicit(&gen, memory_order_acquire);

#ifdef CHECK_BUG
        if (g1 == g2 && g1 != 0) {
            if (v != g1)
                BUG_ON(1);
        }
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

    atomic_store(&gen, 0);
    atomic_store(&idx, 0);
    for (int i = 0; i < SLOTS; i++)
        atomic_store(&slots[i], 0);

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
