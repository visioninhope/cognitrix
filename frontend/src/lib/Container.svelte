<script lang="ts"></script>

<main>
  <slot />
</main>

<style>
  main {
    inline-size: 90%;
    border-radius: 7px;
    background: var(--bg-2);
    position: relative;
    box-shadow: var(--shadow-sm);
    overflow: hidden auto;
    box-sizing: border-box;
    position: relative;
  }

  @media screen and (max-width: 640px) {
    main {
      inline-size: 100vmin;
    }
  }
</style>
